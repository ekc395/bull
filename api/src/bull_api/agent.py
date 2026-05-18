"""Agent: deterministic tool fetch + single-shot synthesis.

Two entry points:
- analyze_ticker(ticker, session, force=False) → always Sonnet, NEVER calls Opus.
  Computes `escalation_recommended` + reasons advisorily.
- deepen_verdict(verdict_id, session) → user-initiated Opus pass on the same facts bundle.

See plan.md → Backend → agent.py for the full flow.
"""

import asyncio
import json
from typing import Any

import anthropic
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import Verdict
from .prompts import ESCALATION_KEYWORDS, SYSTEM_PROMPT_DEEPER, SYSTEM_PROMPT_STANDARD
from .repos import verdicts as vrepo
from .time import trading_day
from .tools.fundamentals import get_fundamentals
from .tools.indicators import compute_indicators
from .tools.news import get_recent_news
from .tools.prices import get_price_history
from .tools.registry import SUBMIT_VERDICT_TOOL
from .tools.support_resistance import find_support_resistance
from .tools.supply_chain import get_supply_chain_context

# Recent daily bars included in the facts bundle. 60 bars ≈ 3 months — enough for
# the LLM to see the medium-term shape without bloating the context window.
PRICE_TAIL_BARS = 60
MAX_TOKENS = 2048


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
    """Parallel fetch all six tool outputs. Indicators + S/R depend on prices."""
    # Phase 1: four independent fetches + prices (needed for phase 2).
    prices_df, fundamentals, news_items, supply_chain = await asyncio.gather(
        asyncio.to_thread(get_price_history, ticker),
        asyncio.to_thread(get_fundamentals, ticker),
        asyncio.to_thread(get_recent_news, ticker),
        asyncio.to_thread(get_supply_chain_context, ticker),
    )
    # Phase 2: indicators and S/R both consume the prices DataFrame.
    indicators, sr = await asyncio.gather(
        asyncio.to_thread(compute_indicators, prices_df),
        asyncio.to_thread(find_support_resistance, prices_df),
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
    }


def _check_escalation(
    confidence: int, news: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Advisory flags. No LLM call. Recommends Opus follow-up if any fire."""
    reasons: list[str] = []
    if confidence < settings.bull_escalation_confidence_threshold:
        reasons.append(f"Low confidence ({confidence}%)")
    for item in news:
        title = (item.get("title") or "").lower()
        for kw in ESCALATION_KEYWORDS:
            if kw in title:
                reasons.append(
                    f"Material news: '{kw}' in \"{(item.get('title') or '')[:100]}\""
                )
                break  # one keyword flag per article max
    return (len(reasons) > 0, reasons)


def _extract_verdict_payload(message: anthropic.types.Message) -> dict[str, Any]:
    """Pull the submit_verdict tool_use block out of the model's response."""
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_verdict":
            return block.input  # type: ignore[return-value]
    raise ValueError("Model did not call submit_verdict")


async def analyze_ticker(
    ticker: str, session: AsyncSession, *, force: bool = False
) -> Verdict:
    """Standard (Sonnet) analysis. Never calls Opus.

    Caching: same ticker, same ET trading day, depth='standard' returns the
    cached row without any LLM cost. Bypass with force=True.
    """
    ticker = ticker.upper()

    if not force:
        cached = await vrepo.get_standard_for_today(ticker, trading_day(), session)
        if cached is not None:
            return cached

    facts = await _build_facts_bundle(ticker)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    # cache_control on both the tool schema and the system prompt — the API
    # caches the longest prefix it can, even if either piece is below the
    # per-block token threshold on its own.
    cached_tool = {**SUBMIT_VERDICT_TOOL, "cache_control": {"type": "ephemeral"}}
    response = await client.messages.create(
        model=settings.bull_primary_model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT_STANDARD,
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
    escalated, reasons = _check_escalation(payload["confidence"], facts["news"])

    verdict = Verdict(
        ticker=ticker,
        action=payload["action"],
        confidence=payload["confidence"],
        headline=payload["headline"],
        report_json=payload["report"],
        key_levels_json=payload["key_levels"],
        # created_at auto-fills via the model's now_utc default.
        model_used=settings.bull_primary_model,
        depth="standard",
        parent_verdict_id=None,
        escalation_recommended=escalated,
        escalation_reasons_json=reasons,
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
        },
        facts_bundle_json=facts,
    )
    return await vrepo.insert(verdict, session)


async def deepen_verdict(verdict_id: int, session: AsyncSession) -> Verdict:
    """User-triggered Opus pass. Reuses the parent verdict's facts_bundle_json — no re-fetching.

    Idempotent: if a deeper child already exists for this parent, returns it
    without spending a second Opus call.
    """
    parent = await vrepo.get_by_id(verdict_id, session)
    if parent is None:
        raise ValueError(f"Verdict {verdict_id} not found")
    if parent.depth != "standard":
        raise ValueError(
            f"Cannot deepen verdict {verdict_id}: depth={parent.depth!r}, expected 'standard'"
        )

    existing = await vrepo.find_deeper_child(verdict_id, session)
    if existing is not None:
        return existing

    facts = parent.facts_bundle_json  # replay the exact bundle the user already saw
    parent_summary = {
        "action": parent.action,
        "confidence": parent.confidence,
        "headline": parent.headline,
        "report": parent.report_json,
        "key_levels": parent.key_levels_json,
        "escalation_reasons": parent.escalation_reasons_json,
    }

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    cached_tool = {**SUBMIT_VERDICT_TOOL, "cache_control": {"type": "ephemeral"}}
    response = await client.messages.create(
        model=settings.bull_deeper_model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT_DEEPER,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[cached_tool],
        tool_choice={"type": "tool", "name": "submit_verdict"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Standard verdict from {parent.model_used} for {parent.ticker}:\n\n"
                    f"```json\n{json.dumps(parent_summary, indent=2, default=str)}\n```\n\n"
                    f"Original facts bundle (as of {facts.get('as_of')}):\n\n"
                    f"```json\n{json.dumps(facts, indent=2, default=str)}\n```\n\n"
                    "Review the flagged concerns and the underlying facts. Affirm, refine, "
                    "or override the prior verdict via submit_verdict. Be specific about "
                    "where you agree or disagree. Include ALL required fields in the tool "
                    "call (action, confidence, headline, report, key_levels) — repeat or "
                    "refine the prior key_levels as needed; do not omit them."
                ),
            }
        ],
    )

    payload = _extract_verdict_payload(response)
    # Deeper passes don't compute their own escalation flags — the user already
    # chose to deepen, so the recommendation is moot. Carry the parent's reasons
    # forward so the audit trail shows what prompted the upgrade.

    # Be lenient: if Opus ever omits a non-action field (rare but observed),
    # fall back to the parent's value rather than failing after spending the call.
    deeper = Verdict(
        ticker=parent.ticker,
        action=payload["action"],
        confidence=payload.get("confidence", parent.confidence),
        headline=payload.get("headline") or parent.headline,
        report_json=payload.get("report") or parent.report_json,
        key_levels_json=payload.get("key_levels") or parent.key_levels_json,
        model_used=settings.bull_deeper_model,
        depth="deeper",
        parent_verdict_id=parent.id,
        escalation_recommended=False,
        escalation_reasons_json=parent.escalation_reasons_json,
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
        },
        facts_bundle_json=facts,  # carried verbatim from the parent
    )
    return await vrepo.insert(deeper, session)
