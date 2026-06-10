"""wyckoff-spring-v1 — Phase C spring out of an accumulation trading range.

Source: the Wyckoff Method (wyckoffanalytics.com/wyckoff-method) — accumulation
schematic #1: after a trading range forms (buying test #8, "base forming"),
Phase C delivers the decisive test of supply. A SPRING undercuts the range
support, trapping late sellers, then closes back inside the range; a
low-volume spring ("no supply") is the method's high-probability long entry,
confirmed by a Sign of Strength toward the range top. Buying test #9 demands
reward ≥ 3× the stop risk — hence the 3:1 floor here (vs 2:1 for the other
strategies). Buying test #7 ("stock stronger than the market") is a
confidence bonus via 20-day relative strength vs SPY.

Deliberate translation choices (the article is discretionary; these pin it
down — revise against the backtest):
  - The shared regime filters require an UPTREND stack, so v1 trades springs
    in RE-accumulation ranges ("stepping stones" in the article), not classic
    post-downtrend bottoms. Phase labeling, P&F cause-counting, and the
    composite-man narrative are not mechanized.
  - Range boundaries come from raw bar highs/lows over RANGE_BARS (excluding
    the spring window), not from the S/R pivot clusters — Wyckoff defines the
    range by its extremes (SC low / AR high), and a spring must undercut the
    actual low.
  - "Quickly reverses" = the last close is back above support while the
    undercut happened within SPRING_LOOKBACK bars. Deeper undercuts than
    SPRING_MAX_DEPTH_PCT are treated as breakdowns, not springs.
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
    reward_risk,
)

NAME = "wyckoff-spring-v1"

# --- tunables (draft values; revise against the backtest) ---------------------
RANGE_BARS = 25  # the trading range / "cause" window (excl. spring window)
SPRING_LOOKBACK = 5  # the undercut must have happened this recently
RANGE_MAX_HEIGHT_PCT = 12.0  # taller than this isn't a base, it's a swing
SPRING_MAX_DEPTH_PCT = 3.0  # undercut deeper than this = breakdown, not spring
NO_SUPPLY_MAX_VOL_RATIO = 1.5  # spring-bar volume vs 20d avg (no selling climax)
STOP_BUFFER_PCT = 0.5  # stop sits just under the spring low (the trap's floor)
MIN_REWARD_RISK = 3.0  # Wyckoff buying test #9: profit >= 3x stop risk

BASE_CONFIDENCE = 60
CONF_BONUS_NO_SUPPLY = 5  # spring volume <= 0.8x average — textbook "no supply"
CONF_BONUS_RS = 5  # buying test #7: outperforming SPY over 20 days
CONF_BONUS_VIX_CALM = 5
MAX_CONFIDENCE = 80


def evaluate(facts: dict[str, Any]) -> StrategyDecision:
    signals = compute_signals({"action": "BUY"}, facts)
    filters = regime_filters(signals)

    last = last_close(facts)
    bars = facts.get("prices") or []
    vol_avg = (facts.get("indicators") or {}).get("volume_20d_avg")

    # Bars need highs/lows/volume; tolerate sparse synthetic bundles.
    usable = [
        b
        for b in bars
        if b.get("high") is not None and b.get("low") is not None and b.get("close") is not None
    ]
    have_bars = len(usable) >= RANGE_BARS + SPRING_LOOKBACK and last is not None

    support = range_high = height_pct = None
    spring_low = depth_pct = spring_vol_ratio = None
    recovered = False
    if have_bars:
        range_bars = usable[-(RANGE_BARS + SPRING_LOOKBACK) : -SPRING_LOOKBACK]
        spring_bars = usable[-SPRING_LOOKBACK:]
        support = min(b["low"] for b in range_bars)
        range_high = max(b["high"] for b in range_bars)
        height_pct = (range_high - support) / last * 100.0
        spring_bar = min(spring_bars, key=lambda b: b["low"])
        spring_low = spring_bar["low"]
        depth_pct = (support - spring_low) / support * 100.0
        if spring_bar.get("volume") is not None and vol_avg:
            spring_vol_ratio = spring_bar["volume"] / vol_avg
        recovered = support < last < range_high  # back inside, not yet broken out

    stop = spring_low * (1 - STOP_BUFFER_PCT / 100.0) if spring_low is not None else None
    rr = (
        reward_risk(last, stop, range_high)
        if last is not None and stop is not None and range_high is not None
        else None
    )

    setup = {
        "base_forming": check(
            have_bars and height_pct is not None and height_pct <= RANGE_MAX_HEIGHT_PCT,
            None if height_pct is None else round(height_pct, 2),
            f"{RANGE_BARS}-bar range height <= {RANGE_MAX_HEIGHT_PCT}%",
        ),
        "spring_undercut": check(
            depth_pct is not None and 0 < depth_pct <= SPRING_MAX_DEPTH_PCT,
            None if depth_pct is None else round(depth_pct, 2),
            f"undercut 0-{SPRING_MAX_DEPTH_PCT}% below range support",
        ),
        "recovered_into_range": check(
            recovered,
            None if last is None or support is None else round(last - support, 2),
            "close back above support, below range top",
        ),
        "no_supply_volume": check(
            spring_vol_ratio is not None and spring_vol_ratio <= NO_SUPPLY_MAX_VOL_RATIO,
            None if spring_vol_ratio is None else round(spring_vol_ratio, 2),
            f"spring-bar volume <= {NO_SUPPLY_MAX_VOL_RATIO}x 20-day average",
        ),
        "reward_risk": check(
            rr is not None and rr >= MIN_REWARD_RISK,
            None if rr is None else round(rr, 2),
            f">= {MIN_REWARD_RISK}:1 to range top (buying test #9)",
        ),
    }

    failed = first_failure(filters, setup)
    if failed is not None:
        return hold(NAME, f"no setup: {failed}", filters, setup, reward_risk=rr)

    confidence = BASE_CONFIDENCE
    if spring_vol_ratio is not None and spring_vol_ratio <= 0.8:
        confidence += CONF_BONUS_NO_SUPPLY
    # Buying test #7 — relative strength vs SPY over the last ~20 bars.
    closes = [b["close"] for b in usable]
    spy_20d = signals.get("spy_pct_change_20d")
    if spy_20d is not None and len(closes) >= 21 and closes[-21]:
        ticker_20d = (closes[-1] / closes[-21] - 1.0) * 100.0
        if ticker_20d > spy_20d:
            confidence += CONF_BONUS_RS
    if signals.get("vix_state") == "calm":
        confidence += CONF_BONUS_VIX_CALM

    return StrategyDecision(
        strategy=NAME,
        candidate_action="BUY",
        base_confidence=min(confidence, MAX_CONFIDENCE),
        reason=(
            f"spring: undercut range support {support:.2f} by {depth_pct:.1f}%, "
            f"recovered to {last:.2f}; {rr:.1f}:1 to range top {range_high:.2f}"
        ),
        filters=filters,
        setup=setup,
        entry=last,
        stop=round(stop, 4),
        target=range_high,
        reward_risk=round(rr, 2),
    )
