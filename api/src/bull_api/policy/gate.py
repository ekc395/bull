"""Phase 3 — Part A gating & sizing (the core deliverable).

A fixed, auditable rule wrapped around the fixed prompt + pipeline (the analysis
model behind it may change; outcomes are pooled across models): given a
verdict's bucketed `Context` and the realized track record of similar past
setups, decide *whether* to act and *how big*. This is where P&L actually comes
from (selectivity + sizing). No persisted model — the "fitted stats" are
recomputed on demand from the outcome table (`fit_stats`).

Three regimes after the hard guardrails pass:
  - **exploit**  bucket has enough samples (n ≥ MIN_SAMPLES) and a positive mean
    favorable return → act, size scaled by edge × confidence, capped.
  - **explore**  bucket is under-sampled (0 < n < MIN_SAMPLES) → act at a small
    size. Paper trading makes exploration free, and it is the engine that
    generates the outcome signal the exploit branch later reads.
  - **cold-start**  no samples for this bucket → guardrails-only at base size.

Guardrails are priors lifted from `checks.py` (Weinstein/Minervini trend, Van
Tharp R:R, earnings-window avoidance): never act on HOLD, on sub-floor
confidence or reward:risk, or inside the 0–5 day earnings window.

`decide` and `fit_stats` are pure and unit-tested; `decision_for_verdict` is the
DB-fed convenience the routers call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..checks import compute_signals
from ..config import settings
from ..scoring import _classify_hit
from .analysis import Outcome
from .features import Context, context_for, effective_reward_risk

if TYPE_CHECKING:
    from ..models import Verdict

# Bump when the rule below changes so persisted decisions stay comparable.
# 0.2.0: fitted stats pool outcomes across models (was: current BULL_MODEL only).
POLICY_VERSION = "0.2.0"

# --- Hard guardrails (priors from checks.py) -------------------------------
CONF_FLOOR = 55  # confidence < 55 is coin-flip / HOLD territory (prompts.py bands)
RR_FLOOR = 1.5  # reward:risk < 1.5 is the poor-RR threshold (checks.py / Van Tharp)

# --- Exploit / explore / sizing knobs --------------------------------------
MIN_SAMPLES = 10  # bucket size before fitted edge is trusted (exploit)
MAX_SIZE_PCT = 5.0  # hard cap on any single position, % of equity
EXPLORE_FRACTION = 0.5  # explore size = base * this
# Sizing horizon: swing trades are judged on the ~1-month leg.
SIZING_HORIZON = 20
# Exploit multiplier shape — size = base * conf_factor * edge_factor, each in
# [1.0, 1.0 + *_GAIN]. EDGE_SAT_PCT is the favorable return at which the edge
# factor saturates.
CONF_GAIN = 0.5
EDGE_GAIN = 0.5
EDGE_SAT_PCT = 5.0


@dataclass(frozen=True)
class BucketStats:
    """Realized track record of the past setups matching a verdict's bucket.

    `mean_favorable_return_pct` is *signed for the action*: positive means the
    action made money on average (for SELL the raw return is negated). This is
    the "fitted stat" the gate exploits; it is recomputed on demand, never
    stored.
    """

    n: int
    mean_favorable_return_pct: float | None
    hit_rate: float | None
    horizon_days: int | None = None


@dataclass(frozen=True)
class PolicyDecision:
    """The gate's output: act / size / why. Mirrors the persisted model fields."""

    act: bool
    size_pct: float  # 0.0 when act is False
    rationale: str
    policy_version: str = POLICY_VERSION


def _favorable_return(action: str, return_pct: float) -> float:
    """Return signed so positive always means the action profited."""
    return return_pct if action == "BUY" else -return_pct


def fit_stats(
    outcomes: list[Outcome],
    context: Context,
    *,
    horizon: int = SIZING_HORIZON,
    threshold: float = 0.0,
) -> BucketStats:
    """Aggregate the realized record of past setups matching `context`.

    Matches on `(action, confidence_band)` at the given horizon — the bucket
    Phase 2 establishes as the headline and the one that actually accumulates
    samples. Returns n=0 when nothing matches (the cold-start signal).
    """
    matching = [
        o
        for o in outcomes
        if o.horizon_days == horizon
        and o.action == context.action
        and o.context.confidence_band == context.confidence_band
    ]
    n = len(matching)
    if n == 0:
        return BucketStats(0, None, None, horizon)

    favs = [_favorable_return(o.action, o.return_pct) for o in matching]
    mean_fav = sum(favs) / n
    hits = [_classify_hit(o.action, o.return_pct, threshold) for o in matching]
    hits = [h for h in hits if h is not None]
    hit_rate = round(sum(hits) / len(hits), 4) if hits else None
    return BucketStats(n, round(mean_fav, 3), hit_rate, horizon)


def _exploit_size(base: float, edge: float, confidence: int) -> float:
    """Scale base size up by edge and confidence, capped at MAX_SIZE_PCT."""
    conf_factor = 1.0 + (confidence - CONF_FLOOR) / (100 - CONF_FLOOR) * CONF_GAIN
    edge_factor = 1.0 + min(edge, EDGE_SAT_PCT) / EDGE_SAT_PCT * EDGE_GAIN
    return min(round(base * conf_factor * edge_factor, 2), MAX_SIZE_PCT)


def decide(
    context: Context,
    stats: BucketStats,
    *,
    confidence: int | None,
    reward_risk_ratio: float | None,
    base_size_pct: float | None = None,
) -> PolicyDecision:
    """Pure gating/sizing decision for one verdict.

    `confidence` and `reward_risk_ratio` are passed raw (not via the coarse
    `Context` bands) so the floors are exact; `context` supplies action, the
    earnings window and the bucket the `stats` were fit on.
    """
    base = settings.bull_position_size_pct if base_size_pct is None else base_size_pct

    def reject(reason: str) -> PolicyDecision:
        return PolicyDecision(False, 0.0, f"reject: {reason}")

    def act(size: float, why: str) -> PolicyDecision:
        return PolicyDecision(True, size, why)

    # --- Hard guardrails ---
    if context.action not in ("BUY", "SELL"):
        return reject(f"no-trade action ({context.action})")
    if confidence is None or confidence < CONF_FLOOR:
        return reject(f"confidence {confidence} < floor {CONF_FLOOR}")
    if reward_risk_ratio is None or reward_risk_ratio < RR_FLOOR:
        rr = "n/a" if reward_risk_ratio is None else f"{reward_risk_ratio:.2f}"
        return reject(f"reward:risk {rr} < floor {RR_FLOOR}")
    if context.earnings_window:
        return reject("inside 0–5 day earnings window")

    # --- Exploit / explore / cold-start ---
    if stats.n >= MIN_SAMPLES:
        edge = stats.mean_favorable_return_pct
        if edge is None or edge <= 0:
            return reject(f"fitted edge {edge}% ≤ 0 over n={stats.n} similar setups")
        size = _exploit_size(base, edge, confidence)
        return act(
            size,
            f"exploit: n={stats.n} similar setups, mean favorable {edge:.2f}% > 0; "
            f"sized {size:.2f}% (conf {confidence})",
        )
    if stats.n > 0:
        size = round(base * EXPLORE_FRACTION, 2)
        return act(
            size,
            f"explore: only n={stats.n} (< {MIN_SAMPLES}) similar setups; "
            f"small size {size:.2f}% to gather outcomes (paper = free)",
        )
    return act(
        round(base, 2),
        f"cold-start: no scored outcomes for this bucket; guardrails passed; "
        f"base size {round(base, 2):.2f}%",
    )


def decision_for_verdict(
    verdict: "Verdict",
    outcomes: list[Outcome],
    *,
    horizon: int = SIZING_HORIZON,
    base_size_pct: float | None = None,
) -> PolicyDecision:
    """Derive context + fit stats from past outcomes, then `decide`.

    The DB-fed entry point the routers use. `outcomes` is the already-collected
    realized track record (`analysis.collect_outcomes`).
    """
    context = context_for(verdict)
    signals = compute_signals({"action": verdict.action}, verdict.facts_bundle_json or {})
    stats = fit_stats(outcomes, context, horizon=horizon)
    return decide(
        context,
        stats,
        confidence=verdict.confidence,
        # Gate the trade that's actually placed: an algo bracket's own R:R, else
        # the S/R geometry for non-algo verdicts. See features.effective_reward_risk.
        reward_risk_ratio=effective_reward_risk(verdict, signals),
        base_size_pct=base_size_pct,
    )
