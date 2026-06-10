"""pullback-v1 — buy weakness within strength.

Trend-following pullback entry (Weinstein Stage 2 / Minervini SEPA school):
an uptrending name that has pulled back near a support cluster with cooled-off
momentum, where the deterministic S/R geometry pays ≥ 2:1 to the next major
resistance. Cannot fire at all-time highs (no resistance above ⇒ no target) —
that regime belongs to the Donchian-breakout style (turtle-20-v1).
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
)

NAME = "pullback-v1"

# --- tunables (draft values; revise against the backtest) ---------------------
SUPPORT_PROXIMITY_PCT = 3.0  # last close at most this far above nearest support
MAX_EXTENSION_PCT = 10.0  # matches checks "extended" threshold (Minervini)
RSI_PULLBACK_BAND = (35.0, 55.0)  # cooled off, not broken
MIN_REWARD_RISK = 2.0  # Van Tharp floor for fresh entries

BASE_CONFIDENCE = 60
CONF_BONUS_RR3 = 5  # reward:risk >= 3
CONF_BONUS_MACD = 5  # MACD histogram already turning up
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
    ext = signals.get("pct_above_sma_50")
    rr = signals.get("reward_risk_ratio")  # nearest support → max resistance

    proximity_pct: float | None = None
    if last is not None and sup is not None and sup["price"] > 0:
        proximity_pct = (last / sup["price"] - 1.0) * 100.0

    lo, hi = RSI_PULLBACK_BAND
    setup = {
        "near_support": check(
            proximity_pct is not None and 0 <= proximity_pct <= SUPPORT_PROXIMITY_PCT,
            None if proximity_pct is None else round(proximity_pct, 2),
            f"<= {SUPPORT_PROXIMITY_PCT}% above nearest support",
        ),
        "not_extended": check(
            ext is not None and ext <= MAX_EXTENSION_PCT,
            None if ext is None else round(ext, 2),
            f"<= {MAX_EXTENSION_PCT}% above SMA-50",
        ),
        "rsi_pullback": check(
            rsi is not None and lo <= rsi <= hi,
            None if rsi is None else round(rsi, 1),
            f"RSI(14) in {lo:g}-{hi:g}",
        ),
        "reward_risk": check(
            rr is not None and rr >= MIN_REWARD_RISK,
            None if rr is None else round(rr, 2),
            f">= {MIN_REWARD_RISK}:1",
        ),
    }

    failed = first_failure(filters, setup)
    if failed is not None:
        return hold(NAME, f"no setup: {failed}", filters, setup, reward_risk=rr)

    confidence = BASE_CONFIDENCE
    if rr is not None and rr >= 3.0:
        confidence += CONF_BONUS_RR3
    macd_hist = signals.get("macd_hist")
    if macd_hist is not None and macd_hist >= 0:
        confidence += CONF_BONUS_MACD
    if sup is not None and (sup.get("touch_count") or 0) >= 3:
        confidence += CONF_BONUS_TOUCHES
    if signals.get("vix_state") == "calm":
        confidence += CONF_BONUS_VIX_CALM

    target = max(r["price"] for r in resistances)  # rr != None guarantees non-empty
    return StrategyDecision(
        strategy=NAME,
        candidate_action="BUY",
        base_confidence=min(confidence, MAX_CONFIDENCE),
        reason=f"pullback to support at {sup['price']:.2f} in an uptrend, {rr:.1f}:1 to {target:.2f}",
        filters=filters,
        setup=setup,
        entry=last,
        stop=sup["price"],
        target=target,
        reward_risk=round(rr, 2),
    )
