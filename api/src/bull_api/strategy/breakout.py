"""breakout-v1 — buy strength.

Donchian-style closing-high breakout on confirming volume (O'Neil/IBD school).
Covers the regime pullback-v1 and bounce-v1 structurally cannot trade: a name
at all-time highs has no overhead resistance, so their R:R is undefined —
here the target falls back to a measured move (entry + 2 × risk).

The breakout window is capped at BREAKOUT_WINDOW_BARS so the rule reads the
same whether the facts bundle carries the short-mode 60-bar tail or a longer
frame (backtester, medium-mode bundles).
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

NAME = "breakout-v1"

# --- tunables (draft values; revise against the backtest) ---------------------
BREAKOUT_WINDOW_BARS = 60  # prior closes the breakout must clear (~3 months)
MIN_PRIOR_BARS = 20  # don't call "breakout" on a stub of history
MIN_VOLUME_RATIO = 1.5  # current volume vs 20-day average (IBD confirmation)
MAX_EXTENSION_PCT = 15.0  # relaxed vs pullback: breakouts run hotter by nature
MAX_RISK_PCT = 8.0  # entry → stop distance as % of entry
MEASURED_MOVE_MULT = 2.0  # target = entry + this × risk when no resistance above
MIN_REWARD_RISK = 2.0

BASE_CONFIDENCE = 60
CONF_BONUS_VOLUME2 = 5  # volume >= 2× average
CONF_BONUS_MACD = 5  # MACD histogram positive
CONF_BONUS_VIX_CALM = 5
MAX_CONFIDENCE = 80


def evaluate(facts: dict[str, Any]) -> StrategyDecision:
    signals = compute_signals({"action": "BUY"}, facts)
    filters = regime_filters(signals)

    last = last_close(facts)
    sup = nearest_support(facts)
    resistances = resistance_levels(facts)
    vol_ratio = signals.get("volume_ratio")
    ext = signals.get("pct_above_sma_50")

    closes = [p.get("close") for p in (facts.get("prices") or [])]
    prior = [c for c in closes[:-1] if c is not None][-BREAKOUT_WINDOW_BARS:]
    prior_high = max(prior) if len(prior) >= MIN_PRIOR_BARS else None
    is_breakout = last is not None and prior_high is not None and last > prior_high

    risk_pct: float | None = None
    if last is not None and sup is not None and last > 0:
        risk_pct = (last - sup["price"]) / last * 100.0

    # Target: real overhead supply when it exists, measured move otherwise.
    target: float | None = None
    rr: float | None = None
    if last is not None and sup is not None and last > sup["price"]:
        risk = last - sup["price"]
        target = max((r["price"] for r in resistances), default=last + MEASURED_MOVE_MULT * risk)
        rr = reward_risk(last, sup["price"], target)

    setup = {
        "closing_high_breakout": check(
            is_breakout,
            None if last is None or prior_high is None else round(last - prior_high, 2),
            f"close > prior {BREAKOUT_WINDOW_BARS}-bar high",
        ),
        "volume_confirms": check(
            vol_ratio is not None and vol_ratio >= MIN_VOLUME_RATIO,
            None if vol_ratio is None else round(vol_ratio, 2),
            f">= {MIN_VOLUME_RATIO}x 20-day average",
        ),
        "not_overextended": check(
            ext is not None and ext <= MAX_EXTENSION_PCT,
            None if ext is None else round(ext, 2),
            f"<= {MAX_EXTENSION_PCT}% above SMA-50",
        ),
        "risk_bounded": check(
            risk_pct is not None and 0 < risk_pct <= MAX_RISK_PCT,
            None if risk_pct is None else round(risk_pct, 2),
            f"stop within {MAX_RISK_PCT}% of entry",
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
    if vol_ratio is not None and vol_ratio >= 2.0:
        confidence += CONF_BONUS_VOLUME2
    macd_hist = signals.get("macd_hist")
    if macd_hist is not None and macd_hist > 0:
        confidence += CONF_BONUS_MACD
    if signals.get("vix_state") == "calm":
        confidence += CONF_BONUS_VIX_CALM

    return StrategyDecision(
        strategy=NAME,
        candidate_action="BUY",
        base_confidence=min(confidence, MAX_CONFIDENCE),
        reason=(
            f"closing-high breakout on {vol_ratio:.1f}x volume, "
            f"{rr:.1f}:1 to {target:.2f}"
        ),
        filters=filters,
        setup=setup,
        entry=last,
        stop=sup["price"],
        target=round(target, 2),
        reward_risk=round(rr, 2),
    )
