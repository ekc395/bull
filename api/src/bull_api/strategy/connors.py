"""connors-rsi2-v1 — Larry Connors' RSI(2) mean reversion.

Source: Connors & Alvarez, "Short Term Trading Strategies That Work" (2008);
widely replicated since (e.g. quantifiedstrategies.com/rsi-2-strategy).
Published results: 75-80% win rates on liquid stocks/indices with 1-3 day
holds. Rules: only above the 200-day SMA (trend filter), buy when RSI(2)
collapses below an oversold threshold, exit on the snap-back within days.

Bracket-framework adaptations (flagged deviations — Connors' own testing
found stops HURT this style, and his exit is "RSI(2) > 65" / "close > 5-day
SMA", neither of which a bracket can express):
  - stop: wide, 2.5 × ATR(14) below entry — far enough to mostly stay out of
    the way while still bounding tail risk (the live system will not run
    stop-less positions).
  - target: 1.0 × ATR above entry — a one-volatility-unit snap-back proxy.
  - time stop: 5 bars — does the "exit regardless" job of Connors' exits.
By construction reward:risk is ~0.4:1; that is the point — this is a
high-win-rate/low-payoff style, the mirror image of pullback/breakout. No
R:R floor is applied; the tournament judges the result.
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

NAME = "connors-rsi2-v1"

# --- tunables (draft values; revise against the backtest) ---------------------
MAX_RSI2 = 10.0  # Connors tested <5 and <10 variants; 10 trades more often
STOP_ATR_MULT = 2.5  # wide on purpose: tight stops break mean reversion
TARGET_ATR_MULT = 1.0  # one volatility unit of snap-back
MAX_HOLD_BARS = 5  # Connors holds are 1-3 days; 5 is the hard cap

BASE_CONFIDENCE = 60
CONF_BONUS_DEEP = 5  # RSI(2) < 5 — Connors' strictest variant
CONF_BONUS_VIX_CALM = 5
MAX_CONFIDENCE = 80


def evaluate(facts: dict[str, Any]) -> StrategyDecision:
    signals = compute_signals({"action": "BUY"}, facts)
    filters = regime_filters(signals)

    last = last_close(facts)
    ind = facts.get("indicators") or {}
    rsi2 = ind.get("rsi_2")
    atr = ind.get("atr_14")
    sma_200 = ind.get("sma_200")

    setup = {
        # Connors' own filter: price above the 200-day (stricter than the
        # shared SMA50>SMA200 stack alone — both must hold).
        "above_sma_200": check(
            last is not None and sma_200 is not None and last > sma_200,
            None if last is None or sma_200 is None else round(last - sma_200, 2),
            "close > 200-day SMA",
        ),
        "rsi2_oversold": check(
            rsi2 is not None and rsi2 < MAX_RSI2,
            None if rsi2 is None else round(rsi2, 1),
            f"RSI(2) < {MAX_RSI2:g}",
        ),
        "atr_known": check(
            atr is not None and atr > 0,
            None if atr is None else round(atr, 2),
            "ATR(14) available for stop/target",
        ),
    }

    failed = first_failure(filters, setup)
    if failed is not None:
        return hold(NAME, f"no setup: {failed}", filters, setup, max_hold=MAX_HOLD_BARS)

    confidence = BASE_CONFIDENCE
    if rsi2 is not None and rsi2 < 5.0:
        confidence += CONF_BONUS_DEEP
    if signals.get("vix_state") == "calm":
        confidence += CONF_BONUS_VIX_CALM

    stop = last - STOP_ATR_MULT * atr
    target = last + TARGET_ATR_MULT * atr
    return StrategyDecision(
        strategy=NAME,
        candidate_action="BUY",
        base_confidence=min(confidence, MAX_CONFIDENCE),
        reason=f"RSI(2) washout at {rsi2:.1f} above the 200-day; snap-back target +{TARGET_ATR_MULT:g} ATR",
        filters=filters,
        setup=setup,
        entry=last,
        stop=round(stop, 4),
        target=round(target, 4),
        reward_risk=round(TARGET_ATR_MULT / STOP_ATR_MULT, 2),
        max_hold_trading_days=MAX_HOLD_BARS,
    )
