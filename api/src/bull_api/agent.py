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
from .prompts import SYSTEM_PROMPT
from .repos import verdicts as vrepo
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

# Recent daily bars included in the facts bundle. 60 bars ≈ 3 months — enough for
# the LLM to see the medium-term shape without bloating the context window.
PRICE_TAIL_BARS = 60
# 4096 leaves headroom for the report's five narrative fields + key_levels.
# 2048 was occasionally truncating the tool call mid-JSON.
MAX_TOKENS = 4096


def _prices_to_records(df: pd.DataFrame, tail: int = PRICE_TAIL_BARS) -> list[dict[str, Any]]:
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


async def _build_facts_bundle(ticker: str) -> dict[str, Any]:
    """Parallel fetch all tool outputs. Indicators + S/R depend on prices;
    market context depends on fundamentals (needs sector/industry to pick
    the right sector ETF)."""
    # Phase 1: independent fetches.
    prices_df, fundamentals, news_items, supply_chain = await asyncio.gather(
        asyncio.to_thread(get_price_history, ticker),
        asyncio.to_thread(get_fundamentals, ticker),
        asyncio.to_thread(get_recent_news, ticker),
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
        "prices": _prices_to_records(prices_df),
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

    Opus 4.7 occasionally emits the report as a single string containing the
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
    ticker: str, session: AsyncSession, *, force: bool = False
) -> Verdict:
    """Run the Opus analysis on the ticker's facts bundle.

    Caching: same ticker, same ET trading day returns the cached row without
    any LLM cost. Bypass with force=True.
    """
    ticker = ticker.upper()

    if not force:
        cached = await vrepo.get_for_today(ticker, trading_day(), session)
        if cached is not None:
            return cached

    facts = await _build_facts_bundle(ticker)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    # cache_control on both the tool schema and the system prompt — the API
    # caches the longest prefix it can, even if either piece is below the
    # per-block token threshold on its own.
    cached_tool = {**SUBMIT_VERDICT_TOOL, "cache_control": {"type": "ephemeral"}}
    response = await client.messages.create(
        model=settings.bull_model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[cached_tool],
        tool_choice={"type": "tool", "name": "submit_verdict"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Facts bundle for {ticker} as of {facts['as_of']}:\n\n"
                    f"```json\n{json.dumps(facts, indent=2, default=str)}\n```\n\n"
                    "Produce the verdict via submit_verdict."
                ),
            }
        ],
    )

    payload = _extract_verdict_payload(response)

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
        report_json=_coerce_report(payload.get("report")),
        key_levels_json=key_levels,
        # created_at auto-fills via the model's now_utc default.
        model_used=settings.bull_model,
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
