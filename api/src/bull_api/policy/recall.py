"""Phase 4 — Part B: outcome-conditioned prompting ("verbal RL" / Reflexion).

Builds a compact "this system's prior calls on similar setups → realized
outcome" block from the system's scored verdicts (pooled across models — the
analysis model churns, the prompt + pipeline persist), so raw verdicts
self-correct in-context. No weight changes; the "reward" arrives as text. Flag-gated
(`BULL_OUTCOME_FEEDBACK`, default off) and appended to the *uncached* user
message in `agent.py`, so prompt caching of the system prompt + tool schema is
preserved.

Similarity is matched on **action-independent setup signals** — at recall time
the model has not yet chosen an action or confidence (that is what we are asking
for), so we cannot bucket on the full `Context`. We match on the trend stack,
sector/market regime, VIX state and earnings window (all computable from the
facts bundle pre-verdict), plus a same-ticker boost, then show each past call's
action / confidence / realized return so the model can calibrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..checks import compute_signals
from ..models import Verdict, VerdictScore
from .analysis import _resolve_model

DEFAULT_K = 6
MAX_BLOCK_CHARS = 1400
# Each matching setup dimension scores 1; same ticker is worth this many dims.
SAME_TICKER_BOOST = 2

# Action-independent setup signals available pre-verdict.
_SETUP_KEYS = (
    "trend_stack_up",
    "sector_above_sma_50",
    "market_above_sma_50",
    "vix_state",
    "earnings_window",
)


@dataclass(frozen=True)
class RecallRow:
    ticker: str
    created_at: datetime
    action: str
    confidence: int | None
    horizon_days: int
    return_pct: float
    setup: dict[str, Any]


def _setup_signature(facts: dict[str, Any]) -> dict[str, Any]:
    """Action-independent setup signals from a facts bundle (None-tolerant)."""
    s = compute_signals({"action": None}, facts or {})
    dte = s.get("days_until_earnings")
    return {
        "trend_stack_up": s.get("trend_stack_up"),
        "sector_above_sma_50": s.get("sector_above_sma_50"),
        "market_above_sma_50": s.get("spy_above_sma_50"),
        "vix_state": s.get("vix_state"),
        "earnings_window": dte is not None and 0 <= dte <= 5,
    }


def _similarity(target: dict[str, Any], other: dict[str, Any], *, same_ticker: bool) -> int:
    """Count matching non-None setup dimensions; boost same-ticker history."""
    score = sum(
        1 for k in _SETUP_KEYS if target.get(k) is not None and target.get(k) == other.get(k)
    )
    if same_ticker:
        score += SAME_TICKER_BOOST
    return score


def _rank(
    target: dict[str, Any], rows: list[RecallRow], ticker: str, k: int
) -> list[RecallRow]:
    """Most-similar first; break ties by recency. Pure."""
    ranked = sorted(
        rows,
        key=lambda r: (
            _similarity(target, r.setup, same_ticker=r.ticker == ticker),
            r.created_at,
        ),
        reverse=True,
    )
    return ranked[:k]


def _format_block(ticker: str, rows: list[RecallRow], max_chars: int) -> str:
    """Render the recall block, trimming rows to stay within `max_chars`."""
    if not rows:
        return ""
    header = (
        "THIS SYSTEM'S PRIOR CALLS ON SIMILAR SETUPS (realized outcomes — calibrate "
        "against them; a track record of misses on this kind of setup should lower "
        "confidence):"
    )
    lines: list[str] = []
    for r in rows:
        sign = "+" if r.return_pct >= 0 else ""
        lines.append(
            f"- {r.ticker} {r.created_at:%Y-%m-%d}: {r.action} "
            f"@conf {r.confidence if r.confidence is not None else '?'} "
            f"→ {sign}{r.return_pct:.1f}% realized over {r.horizon_days}d"
        )
    block = header + "\n" + "\n".join(lines)
    # Trim from the tail (least similar) until within budget.
    while len(block) > max_chars and len(lines) > 1:
        lines.pop()
        block = header + "\n" + "\n".join(lines)
    return block


async def _recall_rows(session: AsyncSession, *, model: str | None = None) -> list[RecallRow]:
    """Join scores to verdicts and derive each one's setup signature.

    Pools every model by default — the track record belongs to the system
    (prompt + pipeline), which outlives any single model.
    """
    stmt = select(VerdictScore, Verdict).join(Verdict, VerdictScore.verdict_id == Verdict.id)
    resolved = _resolve_model(model)
    if resolved is not None:
        stmt = stmt.where(Verdict.model_used == resolved)
    rows = list((await session.execute(stmt)).all())

    sig_cache: dict[int, dict[str, Any]] = {}
    out: list[RecallRow] = []
    for score, verdict in rows:
        sig = sig_cache.get(verdict.id)
        if sig is None:
            sig = _setup_signature(verdict.facts_bundle_json or {})
            sig_cache[verdict.id] = sig
        out.append(
            RecallRow(
                ticker=verdict.ticker,
                created_at=verdict.created_at,
                action=verdict.action,
                confidence=verdict.confidence,
                horizon_days=score.horizon_days,
                return_pct=score.realized_return_pct,
                setup=sig,
            )
        )
    return out


async def similar_outcomes(
    session: AsyncSession,
    ticker: str,
    facts: dict[str, Any],
    *,
    k: int = DEFAULT_K,
    max_chars: int = MAX_BLOCK_CHARS,
    model: str | None = None,
) -> str:
    """The `k` most-similar past scored verdicts as a compact text block.

    Pooled across models by default. Returns "" when there is no scored
    history yet (cold start) — the caller appends nothing.
    """
    target = _setup_signature(facts)
    rows = await _recall_rows(session, model=model)
    return _format_block(ticker, _rank(target, rows, ticker, k), max_chars)
