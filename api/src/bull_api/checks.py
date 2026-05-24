"""Post-verdict sanity checks drawn from established swing-trading literature.

Each validator inspects the (facts, payload) pair and returns a Warning dict
or None. Sources are cited per check so unhelpful ones can be pruned with the
backtest scoring loop later. These are NOT auto-corrections — the verdict
stands as the model returned it; warnings only surface contradictions
between the verdict and its own inputs.

Severity tiers:
  info    — informational, common false-positive in trending markets
  warn    — historical edge against this setup; merits attention
  strong  — pros typically avoid this setup entirely
"""

from typing import Any, Literal, TypedDict

Severity = Literal["info", "warn", "strong"]


class Warning(TypedDict):
    code: str
    severity: Severity
    message: str
    source: str


def _last_close(facts: dict[str, Any]) -> float | None:
    prices = facts.get("prices") or []
    if not prices:
        return None
    return prices[-1].get("close")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _trend_stack_aligned(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """Stage-2 alignment: BUY needs SMA50 > SMA200; SELL the inverse.

    Source: Stan Weinstein ("Secrets for Profiting in Bull and Bear Markets")
    Stage-2 definition; refined by Mark Minervini's SEPA into the 50/150/200
    stacking requirement. Counter-trend trades have measurably lower hit rates
    in equity swing samples.
    """
    action = payload.get("action")
    if action == "HOLD":
        return None
    ind = facts.get("indicators") or {}
    s50, s200 = ind.get("sma_50"), ind.get("sma_200")
    if s50 is None or s200 is None:
        return None
    if action == "BUY" and s50 < s200:
        return {
            "code": "counter_trend_buy",
            "severity": "warn",
            "message": f"BUY into downtrend stack: SMA50 ({s50:.2f}) < SMA200 ({s200:.2f}). Counter-trend buys need an explicit catalyst.",
            "source": "Weinstein Stage 2 / Minervini SEPA",
        }
    if action == "SELL" and s50 > s200:
        return {
            "code": "counter_trend_sell",
            "severity": "warn",
            "message": f"SELL into uptrend stack: SMA50 ({s50:.2f}) > SMA200 ({s200:.2f}).",
            "source": "Weinstein Stage 2 / Minervini SEPA",
        }
    return None


def _sector_confirmation(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """CANSLIM 'L' (Leader/Laggard): BUY requires sector strength.

    Source: William O'Neil, "How to Make Money in Stocks". A bullish single-name
    thesis into a sector ETF below its 50-day SMA is fighting the group.
    """
    if payload.get("action") != "BUY":
        return None
    mc = facts.get("market_context") or {}
    sec = mc.get("sector") or {}
    if sec.get("above_sma_50") is False:
        etf = mc.get("sector_etf")
        pct = sec.get("pct_change_20d")
        return {
            "code": "weak_sector_buy",
            "severity": "warn",
            "message": f"BUY against weak sector: {etf} below 50-day SMA ({pct}% over 20d).",
            "source": "CANSLIM 'L' (O'Neil)",
        }
    return None


def _market_confirmation(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """CANSLIM 'M' (Market direction): ~75% of stocks track the market.

    Source: William O'Neil, "How to Make Money in Stocks". Initiating longs
    when SPY is below its 50-day SMA fights the broader tape.
    """
    if payload.get("action") != "BUY":
        return None
    spy = (facts.get("market_context") or {}).get("spy") or {}
    if spy.get("above_sma_50") is False:
        pct = spy.get("pct_change_20d")
        return {
            "code": "weak_market_buy",
            "severity": "warn",
            "message": f"BUY against weak market: SPY below 50-day SMA ({pct}% over 20d).",
            "source": "CANSLIM 'M' (O'Neil)",
        }
    return None


def _rsi_extreme(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """RSI(14) extremes: BUY at >70 (overbought) or SELL at <30 (oversold).

    Source: J. Welles Wilder Jr., "New Concepts in Technical Trading Systems"
    (1978). Strong trends sustain RSI extremes — this is INFO-level, not a
    block.
    """
    action = payload.get("action")
    if action == "HOLD":
        return None
    rsi = (facts.get("indicators") or {}).get("rsi_14")
    if rsi is None:
        return None
    if action == "BUY" and rsi > 70:
        return {
            "code": "rsi_overbought",
            "severity": "info",
            "message": f"BUY with RSI(14) = {rsi:.1f} (>70 overbought). Mean-reversion risk; strong trends can sustain.",
            "source": "Wilder RSI (1978)",
        }
    if action == "SELL" and rsi < 30:
        return {
            "code": "rsi_oversold",
            "severity": "info",
            "message": f"SELL with RSI(14) = {rsi:.1f} (<30 oversold). Bounce risk.",
            "source": "Wilder RSI (1978)",
        }
    return None


def _macd_against_action(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """MACD histogram sign disagrees with the action.

    Source: Gerald Appel, MACD (1979). The histogram (MACD - signal) is the
    short-term momentum gauge; negative-into-BUY means calling a bottom
    before momentum has confirmed.
    """
    action = payload.get("action")
    if action == "HOLD":
        return None
    hist = (facts.get("indicators") or {}).get("macd_hist")
    if hist is None:
        return None
    if action == "BUY" and hist < 0:
        return {
            "code": "macd_bearish_buy",
            "severity": "warn",
            "message": f"BUY with MACD histogram negative ({hist:.3f}). Momentum has not yet turned up.",
            "source": "MACD (Appel)",
        }
    if action == "SELL" and hist > 0:
        return {
            "code": "macd_bullish_sell",
            "severity": "warn",
            "message": f"SELL with MACD histogram positive ({hist:.3f}). Momentum has not yet turned down.",
            "source": "MACD (Appel)",
        }
    return None


def _extended_from_sma50(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """Price >10% above SMA50: Minervini's "extended" zone — chase-buyer trap.

    Source: Mark Minervini, "Trade Like a Stock Market Wizard". SEPA explicitly
    warns against initiating new positions when extended; sweet spot is
    within ~5% of a rising 50-day.
    """
    if payload.get("action") != "BUY":
        return None
    s50 = (facts.get("indicators") or {}).get("sma_50")
    last = _last_close(facts)
    if s50 is None or last is None or s50 == 0:
        return None
    ext = (last / s50 - 1.0) * 100.0
    if ext > 10:
        return {
            "code": "extended_from_sma50",
            "severity": "warn",
            "message": f"Price {ext:.1f}% above SMA50. Minervini's 'extended' zone — chase-buyer entries historically underperform.",
            "source": "Minervini SEPA",
        }
    return None


def _risk_reward(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """Reward-to-risk ratio < 1.5:1 from the deterministic S/R.

    Source: Van Tharp, "Trade Your Way to Financial Freedom"; standard
    position-sizing literature. Pros target >=2:1; <1.5:1 is the threshold
    where expectancy turns negative for typical win rates (45-55%).
    """
    action = payload.get("action")
    if action == "HOLD":
        return None
    sr = facts.get("support_resistance") or {}
    supports = [s["price"] for s in (sr.get("support") or []) if s.get("price") is not None]
    resistances = [r["price"] for r in (sr.get("resistance") or []) if r.get("price") is not None]
    last = _last_close(facts)
    if not supports or not resistances or last is None:
        return None

    if action == "BUY":
        nearest_sup = max(supports)  # all < last; nearest = max
        target = max(resistances)
        risk, reward = last - nearest_sup, target - last
    else:  # SELL
        nearest_res = min(resistances)  # all >= last; nearest = min
        target = min(supports)
        risk, reward = nearest_res - last, last - target

    if risk <= 0 or reward <= 0:
        return None
    ratio = reward / risk
    if ratio < 1.5:
        return {
            "code": f"poor_rr_{action.lower()}",
            "severity": "warn",
            "message": f"Reward:risk = {ratio:.2f}:1 from deterministic levels. Pros require >= 2:1 (Van Tharp).",
            "source": "Van Tharp position sizing",
        }
    return None


def _earnings_window(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """Initiating positions inside the 0-5 day pre-earnings window.

    Source: institutional swing convention (Minervini, Dan Zanger, etc.).
    Pre-earnings trades are event-driven — a clean technical setup does not
    survive the print. Acceptable only when the earnings reaction IS the
    thesis.
    """
    action = payload.get("action")
    if action == "HOLD":
        return None
    dte = (facts.get("fundamentals") or {}).get("days_until_earnings")
    if dte is None:
        return None
    if 0 <= dte <= 5:
        return {
            "code": "inside_earnings_window",
            "severity": "strong",
            "message": f"{action} with earnings in {dte} day(s). Pre-earnings is a coin-flip unless the earnings reaction IS the thesis.",
            "source": "Minervini / institutional swing convention",
        }
    return None


def _volume_confirmation(payload: dict[str, Any], facts: dict[str, Any]) -> Warning | None:
    """BUY on volume meaningfully below the 20-day average.

    Source: Dow Theory volume principle; codified by O'Neil/IBD. Conviction-
    light entries (especially at/near highs) are statistically more likely
    to fail and get retraced.
    """
    if payload.get("action") != "BUY":
        return None
    ind = facts.get("indicators") or {}
    vc, va = ind.get("volume_current"), ind.get("volume_20d_avg")
    if vc is None or va is None or va == 0:
        return None
    ratio = vc / va
    if ratio < 0.7:
        return {
            "code": "low_volume_buy",
            "severity": "info",
            "message": f"BUY with current volume {ratio:.0%} of 20-day average. Light-volume entries get retraced.",
            "source": "Dow Theory / IBD volume confirmation",
        }
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def validate_verdict(
    payload: dict[str, Any],
    facts: dict[str, Any],
) -> list[Warning]:
    """Run every check; return the non-None warnings."""
    results: list[Warning | None] = [
        _trend_stack_aligned(payload, facts),
        _sector_confirmation(payload, facts),
        _market_confirmation(payload, facts),
        _rsi_extreme(payload, facts),
        _macd_against_action(payload, facts),
        _extended_from_sma50(payload, facts),
        _risk_reward(payload, facts),
        _earnings_window(payload, facts),
        _volume_confirmation(payload, facts),
    ]
    return [w for w in results if w is not None]
