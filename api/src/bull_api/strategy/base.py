"""Deterministic swing-entry strategies: shared types, regime filters, and the
LLM review contract.

In short mode the strategy decides the candidate verdict and the LLM may only
veto (downgrade to HOLD) or shade confidence within ±LLM_SHADE_BAND — enforced
server-side by `enforce_llm_review`, never trusted to the prompt alone.

Every strategy is a pure function `evaluate(facts) -> StrategyDecision` with no
I/O, so the same code path runs live (agent.py) and in the backtester
(bull_api.backtest) over decades of history with no LLM involved.

Backtest contract: the facts bundle's `indicators` and `support_resistance`
are computed over the FULL price frame fetched for the timeframe (~400
calendar days for short), not the 60 bars stored in `facts["prices"]`. A
point-in-time replay must recompute them over the same trailing window —
see `backtest.build_facts_asof`.

Regime filters are shared across strategies (identical hard gates) so the
tournament compares entry logic, not filter strictness. None-handling policy:
trend/SPY/sector/VIX fail CLOSED (missing data → no trade); the earnings
window fails OPEN (None means yfinance has no date — matches
`checks._earnings_window`, which skips when unknown).
"""

from dataclasses import asdict, dataclass
from typing import Any, Callable

from ..checks import Signals

# --- shared tunables --------------------------------------------------------

VIX_BLOCKED_STATES: tuple[str, ...] = ("high",)
EARNINGS_WINDOW: tuple[int, int] = (0, 5)  # trading days before the print
MAX_HOLD_TRADING_DAYS = 20  # time stop; matches the 20d scoring horizon
HOLD_BASE_CONFIDENCE = 60  # candidate confidence when there is no setup
LLM_SHADE_BAND = 15  # LLM may move confidence at most this far from base
MAX_CONFIDENCE = 80  # rule-derived confidence is capped; >80 is earned live


def check(passed: bool, value: Any, threshold: Any) -> dict[str, Any]:
    """One filter/setup line item, JSON-ready for algo_json and the UI."""
    return {"passed": bool(passed), "value": value, "threshold": threshold}


@dataclass(frozen=True)
class StrategyDecision:
    """A strategy's full evaluation of one facts bundle."""

    strategy: str  # e.g. "pullback-v1" (name + version in one tag)
    candidate_action: str  # "BUY" | "HOLD" — long-only v1, never SELL
    base_confidence: int
    reason: str  # human-readable; first failure when HOLD
    filters: dict[str, dict[str, Any]]  # shared regime gates
    setup: dict[str, dict[str, Any]]  # strategy-specific conditions
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    reward_risk: float | None = None
    max_hold_trading_days: int = MAX_HOLD_TRADING_DAYS

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


# Strategy = module-level pure function; the registry lives in __init__.py.
StrategyFn = Callable[[dict[str, Any]], StrategyDecision]


# --- shared regime filters ---------------------------------------------------


def regime_filters(signals: Signals) -> dict[str, dict[str, Any]]:
    """The five hard gates every strategy shares. All are evaluated (no
    short-circuit) so the UI can render the complete checklist."""
    dte = signals.get("days_until_earnings")
    lo, hi = EARNINGS_WINDOW
    return {
        "trend_stack_up": check(
            signals.get("trend_stack_up") is True,
            signals.get("trend_stack_up"),
            "SMA50 > SMA200",
        ),
        "market_above_sma_50": check(
            signals.get("spy_above_sma_50") is True,
            signals.get("spy_above_sma_50"),
            "SPY > 50-day SMA",
        ),
        "sector_above_sma_50": check(
            signals.get("sector_above_sma_50") is True,
            signals.get("sector_above_sma_50"),
            "sector ETF > 50-day SMA",
        ),
        "vix_not_high": check(
            signals.get("vix_state") is not None
            and signals.get("vix_state") not in VIX_BLOCKED_STATES,
            signals.get("vix_state"),
            f"not in {list(VIX_BLOCKED_STATES)}",
        ),
        # Fail-open on None: no earnings date known ⇒ pass.
        "outside_earnings_window": check(
            dte is None or not (lo <= dte <= hi),
            dte,
            f"not {lo}-{hi} days before earnings",
        ),
    }


def first_failure(*check_groups: dict[str, dict[str, Any]]) -> str | None:
    """Name of the first failing check across the given groups, or None."""
    for group in check_groups:
        for name, c in group.items():
            if not c["passed"]:
                return name
    return None


# --- facts-bundle helpers (shared by strategies) ------------------------------


def last_close(facts: dict[str, Any]) -> float | None:
    prices = facts.get("prices") or []
    return prices[-1].get("close") if prices else None


def support_levels(facts: dict[str, Any]) -> list[dict[str, Any]]:
    sr = facts.get("support_resistance") or {}
    return [s for s in (sr.get("support") or []) if s.get("price") is not None]


def resistance_levels(facts: dict[str, Any]) -> list[dict[str, Any]]:
    sr = facts.get("support_resistance") or {}
    return [r for r in (sr.get("resistance") or []) if r.get("price") is not None]


def nearest_support(facts: dict[str, Any]) -> dict[str, Any] | None:
    sups = support_levels(facts)
    return max(sups, key=lambda s: s["price"]) if sups else None


def reward_risk(entry: float, stop: float, target: float) -> float | None:
    """(target - entry) / (entry - stop); None on degenerate geometry.
    Same convention as `checks._reward_risk_ratio` for a BUY."""
    risk, reward = entry - stop, target - entry
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def hold(
    strategy: str,
    reason: str,
    filters: dict[str, dict[str, Any]],
    setup: dict[str, dict[str, Any]],
    *,
    reward_risk: float | None = None,
    max_hold: int = MAX_HOLD_TRADING_DAYS,
) -> StrategyDecision:
    return StrategyDecision(
        strategy=strategy,
        candidate_action="HOLD",
        base_confidence=HOLD_BASE_CONFIDENCE,
        reason=reason,
        filters=filters,
        setup=setup,
        reward_risk=reward_risk,
        max_hold_trading_days=max_hold,
    )


# --- LLM review enforcement ----------------------------------------------------


def enforce_llm_review(
    decision: StrategyDecision,
    llm_action: str,
    llm_confidence: int,
    reasoning: str = "",
) -> tuple[str, int, dict[str, Any]]:
    """Coerce the LLM's output into its allowed moves: confirm the candidate
    (confidence within ±LLM_SHADE_BAND of base) or veto a BUY down to HOLD.

    Returns (final_action, final_confidence, review) where `review` is stored
    under algo_json["llm_review"]. The prompt states these rules; this function
    is what actually guarantees them.
    """
    coercions: list[str] = []
    action = llm_action
    confidence = int(llm_confidence)

    if action not in (decision.candidate_action, "HOLD"):
        # SELL anywhere, or BUY when the candidate is HOLD: not the LLM's call.
        coercions.append("illegal_action")
        action = decision.candidate_action

    veto = decision.candidate_action == "BUY" and action == "HOLD"
    if not veto:
        lo = max(0, decision.base_confidence - LLM_SHADE_BAND)
        hi = min(100, decision.base_confidence + LLM_SHADE_BAND)
        clamped = min(max(confidence, lo), hi)
        if clamped != confidence:
            coercions.append("confidence_clamped")
            confidence = clamped
    # On veto the LLM's confidence stands as-is — it describes the HOLD, and
    # the policy gate never trades HOLDs anyway.

    veto_reason: str | None = None
    if veto:
        first_line = (reasoning or "").strip().splitlines()[0:1]
        if first_line and first_line[0].upper().startswith("VETO:"):
            veto_reason = first_line[0][5:].strip()

    review = {
        "veto": veto,
        "veto_reason": veto_reason,
        "raw_llm_action": llm_action,
        "raw_llm_confidence": int(llm_confidence),
        "coercions": coercions,
    }
    return action, confidence, review
