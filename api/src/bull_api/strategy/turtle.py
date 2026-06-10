"""turtle-20-v1 — the Turtles' System 1: 20-day breakout with a 2N stop.

Source: Richard Dennis / William Eckhardt's 1983 Turtle experiment (rules
published by Curtis Faith, "The Original Turtle Trading Rules"; see also
tradingblox.com/Manuals/UsersGuideHTML/turtlesystem.htm). System 1 enters on
a 20-day price-high breakout with the stop 2 × N (ATR) below entry. The
documented caveat — modern replications find S1 whipsaw-prone vs the 55-day
System 2 — is exactly the kind of claim this tournament can check.

Bracket-framework adaptations (flagged deviations):
  - exit: the Turtles trailed a 10-day-low exit and pyramided every ½N; the
    bracket proxy is a 2R target (entry + 2 × the 2N risk = +4 ATR) plus the
    shared 20-bar time stop. No pyramiding.
  - entry: signal on the daily close above the prior 20-bar high, filled at
    the next open (the Turtles entered intraday on the tick through the
    level).
Pure ATR risk geometry, no volume condition, no S/R levels — a clean test of
"does the classic turtle entry still carry edge". (It outlived breakout-v1,
a 60-bar volume-confirmed variant pruned in the 2026-06 tournament.)
"""

from typing import Any

from ..checks import compute_signals
from .base import (
    StrategyDecision,
    check,
    first_failure,
    hold,
    last_close,
    regime_filters,
)

NAME = "turtle-20-v1"

# --- tunables (draft values; revise against the backtest) ---------------------
DONCHIAN_BARS = 20  # System 1's breakout window
MIN_PRIOR_BARS = 20  # need the full window before calling a breakout
STOP_ATR_MULT = 2.0  # the Turtles' 2N
TARGET_R_MULT = 2.0  # bracket proxy for the trailing 10-day-low exit

BASE_CONFIDENCE = 60
CONF_BONUS_MACD = 5  # momentum already positive
CONF_BONUS_VIX_CALM = 5
MAX_CONFIDENCE = 80


def evaluate(facts: dict[str, Any]) -> StrategyDecision:
    signals = compute_signals({"action": "BUY"}, facts)
    filters = regime_filters(signals)

    last = last_close(facts)
    ind = facts.get("indicators") or {}
    atr = ind.get("atr_14")

    bars = facts.get("prices") or []
    highs = [b.get("high") for b in bars[:-1] if b.get("high") is not None]
    prior_high = max(highs[-DONCHIAN_BARS:]) if len(highs) >= MIN_PRIOR_BARS else None
    is_breakout = last is not None and prior_high is not None and last > prior_high

    setup = {
        "donchian_20_breakout": check(
            is_breakout,
            None if last is None or prior_high is None else round(last - prior_high, 2),
            f"close > prior {DONCHIAN_BARS}-bar high",
        ),
        "atr_known": check(
            atr is not None and atr > 0,
            None if atr is None else round(atr, 2),
            "ATR(14) available for the 2N stop",
        ),
    }

    failed = first_failure(filters, setup)
    if failed is not None:
        return hold(NAME, f"no setup: {failed}", filters, setup)

    confidence = BASE_CONFIDENCE
    macd_hist = signals.get("macd_hist")
    if macd_hist is not None and macd_hist > 0:
        confidence += CONF_BONUS_MACD
    if signals.get("vix_state") == "calm":
        confidence += CONF_BONUS_VIX_CALM

    risk = STOP_ATR_MULT * atr
    stop = last - risk
    target = last + TARGET_R_MULT * risk
    return StrategyDecision(
        strategy=NAME,
        candidate_action="BUY",
        base_confidence=min(confidence, MAX_CONFIDENCE),
        reason=(
            f"20-day breakout above {prior_high:.2f}; 2N stop at {stop:.2f}, "
            f"{TARGET_R_MULT:g}R target {target:.2f}"
        ),
        filters=filters,
        setup=setup,
        entry=last,
        stop=round(stop, 4),
        target=round(target, 4),
        reward_risk=TARGET_R_MULT,
    )
