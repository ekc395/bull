"""Agent: deterministic tool fetch + single-shot synthesis.

One entry point: analyze_ticker(ticker, session, force=False) → Opus pass on a
parallel-fetched facts bundle.

See plan.md → Backend → agent.py for the full flow.
"""

import asyncio
import json
import logging
import re
from typing import Any

import anthropic
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from .checks import validate_verdict
from .config import settings
from .models import Verdict
from .policy.recall import similar_outcomes
from .prompts import SYSTEM_PROMPT_BASE, for_timeframe, render_candidate_block
from .repos import verdicts as vrepo
from .strategy import REGISTRY, enforce_llm_review
from .time import trading_day

logger = logging.getLogger(__name__)
from .tools.fundamentals import get_fundamentals
from .tools.indicators import compute_indicators
from .tools.market_context import get_market_context
from .tools.news import get_recent_news
from .tools.prices import get_price_history
from .tools.registry import SUBMIT_VERDICT_TOOL
from .tools.support_resistance import find_support_resistance
from .tools.supply_chain import get_supply_chain_context

# Recent daily bars included in the facts bundle, by user-selected timeframe.
# Long-horizon analyses need more history for trend/regime context; short needs
# only the near-term shape so the context window stays compact.
_PRICE_TAIL_BARS: dict[str, int] = {"short": 60, "medium": 250, "long": 750}
# yfinance fetch window (calendar days). Has to be enough to yield the tail
# above plus headroom for SMA-200 warmup on long.
_PRICE_LOOKBACK_DAYS: dict[str, int] = {"short": 400, "medium": 400, "long": 1100}
# Recent-news window (calendar days), by timeframe.
_NEWS_DAYS: dict[str, int] = {"short": 7, "medium": 30, "long": 90}

# 4096 leaves headroom for the report's five narrative fields + key_levels.
# 2048 was occasionally truncating the tool call mid-JSON.
MAX_TOKENS = 4096


def _tf(d: dict[str, int], timeframe: str) -> int:
    """Look up a per-timeframe window with a safe fallback to medium."""
    return d.get(timeframe, d["medium"])


class InsufficientCreditsError(Exception):
    """Anthropic returned a credit-balance-too-low error. Routers map this to HTTP 402."""


def _prices_to_records(df: pd.DataFrame, tail: int) -> list[dict[str, Any]]:
    """OHLCV DataFrame → list of dicts, last `tail` bars only."""
    records: list[dict[str, Any]] = []
    for ts, row in df.tail(tail).iterrows():
        records.append(
            {
                "date": ts.date().isoformat(),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
        )
    return records


async def _build_facts_bundle(ticker: str, timeframe: str) -> dict[str, Any]:
    """Parallel fetch all tool outputs. Indicators + S/R depend on prices;
    market context depends on fundamentals (needs sector/industry to pick
    the right sector ETF).

    The `timeframe` controls how much history is fetched and how far back the
    news window goes — short looks ~3 months / 7 days, long looks ~3 years /
    90 days.
    """
    lookback_days = _tf(_PRICE_LOOKBACK_DAYS, timeframe)
    news_days = _tf(_NEWS_DAYS, timeframe)
    tail_bars = _tf(_PRICE_TAIL_BARS, timeframe)

    # Phase 1: independent fetches.
    prices_df, fundamentals, news_items, supply_chain = await asyncio.gather(
        asyncio.to_thread(get_price_history, ticker, lookback_days),
        asyncio.to_thread(get_fundamentals, ticker),
        asyncio.to_thread(get_recent_news, ticker, news_days),
        asyncio.to_thread(get_supply_chain_context, ticker),
    )
    # Phase 2: indicators + S/R consume prices; market_context consumes sector/industry.
    indicators, sr, market = await asyncio.gather(
        asyncio.to_thread(compute_indicators, prices_df),
        asyncio.to_thread(find_support_resistance, prices_df),
        asyncio.to_thread(
            get_market_context,
            fundamentals.get("sector"),
            fundamentals.get("industry"),
        ),
    )
    return {
        "ticker": ticker.upper(),
        "as_of": trading_day().isoformat(),
        "timeframe": timeframe,
        "prices": _prices_to_records(prices_df, tail=tail_bars),
        "indicators": indicators,
        "support_resistance": sr,
        "fundamentals": fundamentals,
        "news": news_items,
        "supply_chain": supply_chain,
        "market_context": market,
    }


def _extract_verdict_payload(message: anthropic.types.Message) -> dict[str, Any]:
    """Pull the submit_verdict tool_use block out of the model's response."""
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_verdict":
            return block.input  # type: ignore[return-value]
    raise ValueError("Model did not call submit_verdict")


_REPORT_FIELDS = (
    "technical",
    "fundamentals_and_supply_chain",
    "news_sentiment",
    "risks",
    "reasoning",
)
_PARAM_TAG_RE = re.compile(
    # Opus emits opening `<parameter name="X">` tags but sometimes omits the
    # closing `</parameter>`. Match either a balanced close OR the next
    # parameter opener OR end-of-string.
    r'<parameter\s+name="([^"]+)"\s*>(.*?)(?:</parameter>|(?=<parameter\s+name=")|\Z)',
    re.DOTALL,
)


def _coerce_report(value: Any) -> dict[str, str]:
    """Defensively normalize the `report` tool input.

    Opus occasionally emits the report as a single string containing the
    internal `<parameter name="...">...</parameter>` XML format instead of a
    JSON object. Parse those tags back out and pad missing fields with empty
    strings so the response schema stays valid.
    """
    if isinstance(value, dict):
        out = {k: str(v) for k, v in value.items() if isinstance(v, str)}
    elif isinstance(value, str):
        out = {m.group(1): m.group(2).strip() for m in _PARAM_TAG_RE.finditer(value)}
        if not out:
            out = {"reasoning": value.strip()}
    else:
        out = {}
    for k in _REPORT_FIELDS:
        if not out.get(k):
            out[k] = ""
    return {k: out[k] for k in _REPORT_FIELDS}


async def analyze_ticker(
    ticker: str, session: AsyncSession, *, force: bool = False, timeframe: str = "medium"
) -> Verdict:
    """Run the Opus analysis on the ticker's facts bundle.

    Caching: same `(ticker, trading day, timeframe)` returns the cached row
    without any LLM cost. Bypass with force=True. The `timeframe` controls
    the prompt variant, the price-tail bar count, and the news-lookback days.
    """
    ticker = ticker.upper()
    if timeframe not in _PRICE_TAIL_BARS:
        timeframe = "medium"

    if not force:
        cached = await vrepo.get_for_today(ticker, trading_day(), session, timeframe=timeframe)
        if cached is not None:
            return cached

    facts = await _build_facts_bundle(ticker, timeframe)

    # Algorithm-first short mode: every registered strategy evaluates the
    # bundle (pure functions — free); the ACTIVE one supplies the candidate
    # the LLM may only confirm (±LLM_SHADE_BAND) or veto down to HOLD.
    strategy_decisions = None
    active_decision = None
    active_name = None
    if timeframe == "short":
        strategy_decisions = {name: fn(facts) for name, fn in REGISTRY.items()}
        active_name = settings.bull_active_strategy
        active_decision = strategy_decisions.get(active_name)
        if active_decision is None:
            active_name = next(iter(REGISTRY))
            active_decision = strategy_decisions[active_name]
            logger.warning(
                "BULL_ACTIVE_STRATEGY %r is not registered; falling back to %s",
                settings.bull_active_strategy,
                active_name,
            )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    # cache_control on the tool schema and the base system prompt — the
    # base is shared across timeframes so it caches; the timeframe blurb
    # is small (~600 tokens) and appended uncached.
    cached_tool = {**SUBMIT_VERDICT_TOOL, "cache_control": {"type": "ephemeral"}}

    # Phase 4 (Part B), flag-gated: append the model's own past verdict→outcome
    # track record for similar setups to the *uncached* user message (preserves
    # prompt caching of the system prompt + tool schema). Empty on cold start.
    user_message = (
        f"Facts bundle for {ticker} as of {facts['as_of']} "
        f"(holding period: {timeframe}):\n\n"
        f"```json\n{json.dumps(facts, indent=2, default=str)}\n```\n\n"
    )
    if active_decision is not None:
        user_message += render_candidate_block(active_decision.to_json()) + "\n\n"
    if settings.bull_outcome_feedback:
        recall = await similar_outcomes(session, ticker, facts)
        if recall:
            user_message += recall + "\n\n"
    user_message += "Produce the verdict via submit_verdict."

    try:
        response = await client.messages.create(
            model=settings.bull_model,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT_BASE,
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": for_timeframe(timeframe),
                },
            ],
            tools=[cached_tool],
            tool_choice={"type": "tool", "name": "submit_verdict"},
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.BadRequestError as e:
        if "credit balance" in str(e).lower():
            raise InsufficientCreditsError(
                "Insufficient Anthropic API credits. Add credits at "
                "console.anthropic.com to continue."
            ) from e
        raise

    payload = _extract_verdict_payload(response)
    report = _coerce_report(payload.get("report"))

    # Short mode: coerce the LLM's output into its allowed moves BEFORE the
    # sanity checks run, so warnings (and the stored verdict) describe the
    # action that is actually persisted. The review record lands in algo_json.
    llm_review = None
    if active_decision is not None:
        final_action, final_confidence, llm_review = enforce_llm_review(
            active_decision,
            payload.get("action", "HOLD"),
            int(payload.get("confidence", active_decision.base_confidence)),
            report["reasoning"],
        )
        if llm_review["coercions"]:
            logger.warning(
                "short-mode LLM output coerced [%s]: %s (raw %s/%s → %s/%s)",
                ticker,
                ",".join(llm_review["coercions"]),
                llm_review["raw_llm_action"],
                llm_review["raw_llm_confidence"],
                final_action,
                final_confidence,
            )
        payload["action"], payload["confidence"] = final_action, final_confidence

    # Post-verdict sanity checks. Surface contradictions between the verdict
    # and its own inputs; do not auto-correct (see checks.py for sources).
    warnings = validate_verdict(payload, facts)
    if warnings:
        for w in warnings:
            logger.info(
                "verdict warning [%s] %s/%s: %s",
                ticker,
                w["severity"],
                w["code"],
                w["message"],
            )

    # Opus occasionally drops `key_levels` despite the schema marking it required.
    # Fall back to the deterministic S/R in the facts bundle — same shape.
    key_levels = payload.get("key_levels") or facts["support_resistance"]

    verdict = Verdict(
        ticker=ticker,
        action=payload["action"],
        confidence=payload["confidence"],
        headline=payload["headline"],
        report_json=report,
        key_levels_json=key_levels,
        # created_at auto-fills via the model's now_utc default.
        timeframe=timeframe,
        model_used=settings.bull_model,
        candidate_action=active_decision.candidate_action if active_decision else None,
        candidate_confidence=active_decision.base_confidence if active_decision else None,
        algo_json=(
            {
                "active_strategy": active_name,
                "evaluations": {
                    name: d.to_json() for name, d in strategy_decisions.items()
                },
                "llm_review": llm_review,
            }
            if strategy_decisions
            else None
        ),
        raw_response_json={
            "stop_reason": response.stop_reason,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_creation_input_tokens": getattr(
                    response.usage, "cache_creation_input_tokens", 0
                ),
                "cache_read_input_tokens": getattr(
                    response.usage, "cache_read_input_tokens", 0
                ),
            },
            "internal_warnings": warnings,
        },
        facts_bundle_json=facts,
    )
    return await vrepo.insert(verdict, session)
