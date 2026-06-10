"""bounce-v1 — oversold reversion inside an uptrend.

Mean-reversion long: an uptrending name (regime filters require the trend
stack) washed out to RSI ≤ 35 right at a support cluster. Targets the NEAREST
resistance — reversion trades take the first exit, they don't ride trends —
so the R:R floor is lower (1.5 vs 2.0 for the trend-following entries).
Like pullback-v1 it needs overhead resistance to price a target, so it cannot
fire at all-time highs (and an uptrending name at RSI 35 rarely is).
"""

from typing import Any

from ..checks import compute_signals
from .base import (
    StrategyDecision,
    check,
    first_failure,
    hold,
    last_close,
    nearest_support,
    regime_filters,
    resistance_levels,
    reward_risk,
)

NAME = "bounce-v1"

# --- tunables (draft values; revise against the backtest) ---------------------
MAX_RSI = 35.0  # washed out (Wilder oversold neighborhood)
SUPPORT_PROXIMITY_PCT = 3.0  # last close at most this far above nearest support
MIN_REWARD_RISK = 1.5  # nearer target → lower floor than trend entries

BASE_CONFIDENCE = 60
CONF_BONUS_RSI30 = 5  # truly oversold (RSI <= 30)
CONF_BONUS_TOUCHES = 5  # nearest support touched >= 3 times
CONF_BONUS_VIX_CALM = 5
MAX_CONFIDENCE = 80


def evaluate(facts: dict[str, Any]) -> StrategyDecision:
    signals = compute_signals({"action": "BUY"}, facts)
    filters = regime_filters(signals)

    last = last_close(facts)
    sup = nearest_support(facts)
    resistances = resistance_levels(facts)
    rsi = signals.get("rsi_14")

    proximity_pct: float | None = None
    if last is not None and sup is not None and sup["price"] > 0:
        proximity_pct = (last / sup["price"] - 1.0) * 100.0

    # Reversion target: the FIRST overhead level, not the furthest.
    target = min((r["price"] for r in resistances), default=None)
    rr: float | None = None
    if last is not None and sup is not None and target is not None:
        rr = reward_risk(last, sup["price"], target)

    setup = {
        "oversold": check(
            rsi is not None and rsi <= MAX_RSI,
            None if rsi is None else round(rsi, 1),
            f"RSI(14) <= {MAX_RSI:g}",
        ),
        "near_support": check(
            proximity_pct is not None and 0 <= proximity_pct <= SUPPORT_PROXIMITY_PCT,
            None if proximity_pct is None else round(proximity_pct, 2),
            f"<= {SUPPORT_PROXIMITY_PCT}% above nearest support",
        ),
        "reward_risk": check(
            rr is not None and rr >= MIN_REWARD_RISK,
            None if rr is None else round(rr, 2),
            f">= {MIN_REWARD_RISK}:1 to nearest resistance",
        ),
    }

    failed = first_failure(filters, setup)
    if failed is not None:
        return hold(NAME, f"no setup: {failed}", filters, setup, reward_risk=rr)

    confidence = BASE_CONFIDENCE
    if rsi is not None and rsi <= 30.0:
        confidence += CONF_BONUS_RSI30
    if sup is not None and (sup.get("touch_count") or 0) >= 3:
        confidence += CONF_BONUS_TOUCHES
    if signals.get("vix_state") == "calm":
        confidence += CONF_BONUS_VIX_CALM

    return StrategyDecision(
        strategy=NAME,
        candidate_action="BUY",
        base_confidence=min(confidence, MAX_CONFIDENCE),
        reason=(
            f"oversold bounce off support at {sup['price']:.2f} (RSI {rsi:.0f}), "
            f"{rr:.1f}:1 to {target:.2f}"
        ),
        filters=filters,
        setup=setup,
        entry=last,
        stop=sup["price"],
        target=target,
        reward_risk=round(rr, 2),
    )
