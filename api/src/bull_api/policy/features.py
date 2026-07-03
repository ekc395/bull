"""Bucketed decision context for a verdict, derived lazily from stored JSON.

`context_for(verdict)` reads the verdict's persisted `facts_bundle_json` (plus
its action/confidence/timeframe) and runs it back through the *same*
`checks.compute_signals` the warnings use, then buckets the continuous signals
into a small, stable `Context`. Because everything is recomputed from already-
stored fields, existing verdicts are covered with **no backfill** and no
migration.

The buckets are deliberately coarse: with a few hundred scored verdicts, fine
bins are noise. Phase 2 (`analysis.py`) aggregates realized outcomes per
`Context.bucket_key()`; Phase 3 (`gate.py`) reads the fitted per-bucket stats to
gate and size. Keep the binning here in one place so calibration and gating
agree on what a "context" is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..checks import Signals, compute_signals

if TYPE_CHECKING:
    from ..models import Verdict


def confidence_band(confidence: int | None) -> str | None:
    """Bucket a 0–100 confidence into the prompts.py reference bands."""
    if confidence is None:
        return None
    if confidence >= 85:
        return "85-100"
    if confidence >= 70:
        return "70-84"
    if confidence >= 55:
        return "55-69"
    if confidence >= 40:
        return "40-54"
    return "0-39"


def reward_risk_band(ratio: float | None) -> str:
    """Bucket the reward:risk ratio. 'na' when no deterministic levels apply."""
    if ratio is None:
        return "na"
    if ratio < 1.0:
        return "<1"
    if ratio < 2.0:
        return "1-2"
    if ratio < 3.0:
        return "2-3"
    return ">=3"


def effective_reward_risk(verdict: "Verdict", signals: Signals | None = None) -> float | None:
    """The reward:risk the trade will actually run on.

    Short-mode algo verdicts execute the active strategy's ATR bracket, whose
    reward:risk is fixed by the rule (e.g. turtle's 2R target) — not the S/R
    geometry `compute_signals` derives. Both the gate's RR guardrail and the
    outcome bucketing should judge the trade that gets placed, so prefer the
    active strategy's own `reward_risk`; fall back to the S/R ratio for non-algo
    (long-mode / pre-strategy) verdicts.
    """
    algo = getattr(verdict, "algo_json", None) or {}
    active_eval = (algo.get("evaluations") or {}).get(algo.get("active_strategy") or "")
    if active_eval and active_eval.get("reward_risk") is not None:
        return active_eval["reward_risk"]
    if signals is None:
        signals = compute_signals({"action": verdict.action}, verdict.facts_bundle_json or {})
    return signals.get("reward_risk_ratio")


@dataclass(frozen=True)
class Context:
    """Coarse, stable bucketing of a verdict's setup for outcome aggregation.

    Categorical/boolean fields only — these are the keys the calibration and
    edge tables group on. `None` means the underlying signal was unavailable
    (thin data); it is preserved as its own bucket rather than guessed.
    """

    action: str | None
    timeframe: str | None
    confidence_band: str | None
    reward_risk_band: str
    trend_aligned: bool | None
    sector_above_sma_50: bool | None
    market_above_sma_50: bool | None  # SPY
    vix_state: str | None
    earnings_window: bool  # action initiated 0–5 trading days before earnings

    def bucket_key(self) -> tuple:
        """Hashable grouping key for the Phase-2 edge table."""
        return (
            self.action,
            self.timeframe,
            self.confidence_band,
            self.reward_risk_band,
            self.trend_aligned,
            self.sector_above_sma_50,
            self.market_above_sma_50,
            self.vix_state,
            self.earnings_window,
        )


def context_for(verdict: "Verdict") -> Context:
    """Derive the bucketed `Context` for a stored verdict.

    Recomputes signals from `verdict.facts_bundle_json` so the R:R band,
    trend/sector/market booleans, vix_state and earnings window match exactly
    what `checks.py` saw at verdict time — one source of truth, lazily.
    """
    facts: dict[str, Any] = verdict.facts_bundle_json or {}
    signals = compute_signals({"action": verdict.action}, facts)

    dte = signals.get("days_until_earnings")
    earnings_window = dte is not None and 0 <= dte <= 5

    return Context(
        action=verdict.action,
        timeframe=verdict.timeframe,
        confidence_band=confidence_band(verdict.confidence),
        reward_risk_band=reward_risk_band(effective_reward_risk(verdict, signals)),
        trend_aligned=signals.get("trend_aligned"),
        sector_above_sma_50=signals.get("sector_above_sma_50"),
        market_above_sma_50=signals.get("spy_above_sma_50"),
        vix_state=signals.get("vix_state"),
        earnings_window=earnings_window,
    )
