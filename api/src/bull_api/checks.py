"""Post-verdict sanity checks drawn from established swing-trading literature.

The raw + derived signals each check needs are computed **once** by
`compute_signals(payload, facts)`; every validator then consumes that one dict.
This keeps the warnings and the learning layer's features
(`policy/features.py`) reading from a single source of truth — the R:R ratio,
trend stack, sector/market confirmation, RSI/MACD, extension, earnings window
and volume are defined in exactly one place.

Each validator inspects the signals and returns a Warning dict or None. Sources
are cited per check so unhelpful ones can be pruned with the backtest scoring
loop later. These are NOT auto-corrections — the verdict stands as the model
returned it; warnings only surface contradictions between the verdict and its
own inputs.

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


class Signals(TypedDict, total=False):
    """One verdict's decision-relevant signals, derived from its facts bundle.

    Direction-aware fields (`trend_aligned`, `macd_aligned`, `reward_risk_ratio`)
    are computed relative to the verdict's own action; raw fields
    (`trend_stack_up`, `macd_hist`, `pct_above_sma_50`) are action-independent.
    Every value is `None`-tolerant: missing upstream data yields `None`, and
    consumers skip rather than guess.
    """

    action: str | None
    last_close: float | None
    # trend stack
    sma_50: float | None
    sma_200: float | None
    trend_stack_up: bool | None  # SMA50 > SMA200, regardless of action
    trend_aligned: bool | None  # stack agrees with the action's direction
    # momentum
    rsi_14: float | None
    macd_hist: float | None
    macd_aligned: bool | None  # histogram sign agrees with the action
    # extension
    pct_above_sma_50: float | None  # (last/SMA50 - 1) * 100
    extended: bool | None  # > 10% above SMA50
    # risk / reward (direction-aware, from deterministic S/R)
    reward_risk_ratio: float | None
    # market structure
    spy_above_sma_50: bool | None
    spy_pct_change_20d: float | None
    sector_etf: str | None
    sector_above_sma_50: bool | None
    sector_pct_change_20d: float | None
    vix_level: float | None
    vix_state: str | None
    # event
    days_until_earnings: int | None
    # volume
    volume_ratio: float | None  # current / 20-day average


def _last_close(facts: dict[str, Any]) -> float | None:
    prices = facts.get("prices") or []
    if not prices:
        return None
    return prices[-1].get("close")


def _reward_risk_ratio(action: str | None, facts: dict[str, Any]) -> float | None:
    """Reward-to-risk ratio from the deterministic support/resistance levels.

    BUY risks down to the nearest support and targets the furthest resistance;
    SELL is the mirror. Returns None when levels or a last close are missing,
    or when either leg is non-positive (degenerate geometry).
    """
    if action not in ("BUY", "SELL"):
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
    return reward / risk


def compute_signals(payload: dict[str, Any], facts: dict[str, Any]) -> Signals:
    """Derive every decision-relevant signal from one (payload, facts) pair.

    Pure and side-effect-free. The single source of truth for both the warning
    validators below and the policy/feature layer.
    """
    action = payload.get("action")
    ind = facts.get("indicators") or {}
    mc = facts.get("market_context") or {}
    spy = mc.get("spy") or {}
    sec = mc.get("sector") or {}
    fund = facts.get("fundamentals") or {}

    last = _last_close(facts)
    s50, s200 = ind.get("sma_50"), ind.get("sma_200")
    hist = ind.get("macd_hist")

    # trend stack
    trend_stack_up: bool | None = None
    trend_aligned: bool | None = None
    if s50 is not None and s200 is not None:
        trend_stack_up = s50 > s200
        if action == "BUY":
            trend_aligned = trend_stack_up
        elif action == "SELL":
            trend_aligned = not trend_stack_up

    # momentum
    macd_aligned: bool | None = None
    if hist is not None:
        if action == "BUY":
            macd_aligned = hist >= 0
        elif action == "SELL":
            macd_aligned = hist <= 0

    # extension from SMA50
    pct_above_sma_50: float | None = None
    extended: bool | None = None
    if s50 is not None and last is not None and s50 != 0:
        pct_above_sma_50 = (last / s50 - 1.0) * 100.0
        extended = pct_above_sma_50 > 10

    # volume ratio
    vc, va = ind.get("volume_current"), ind.get("volume_20d_avg")
    volume_ratio: float | None = vc / va if (vc is not None and va) else None

    return {
        "action": action,
        "last_close": last,
        "sma_50": s50,
        "sma_200": s200,
        "trend_stack_up": trend_stack_up,
        "trend_aligned": trend_aligned,
        "rsi_14": ind.get("rsi_14"),
        "macd_hist": hist,
        "macd_aligned": macd_aligned,
        "pct_above_sma_50": pct_above_sma_50,
        "extended": extended,
        "reward_risk_ratio": _reward_risk_ratio(action, facts),
        "spy_above_sma_50": spy.get("above_sma_50"),
        "spy_pct_change_20d": spy.get("pct_change_20d"),
        "sector_etf": mc.get("sector_etf"),
        "sector_above_sma_50": sec.get("above_sma_50"),
        "sector_pct_change_20d": sec.get("pct_change_20d"),
        "vix_level": mc.get("vix_level"),
        "vix_state": mc.get("vix_state"),
        "days_until_earnings": fund.get("days_until_earnings"),
        "volume_ratio": volume_ratio,
    }


# ---------------------------------------------------------------------------
# Individual checks (each consumes the shared Signals)
# ---------------------------------------------------------------------------


def _trend_stack_aligned(s: Signals) -> Warning | None:
    """Stage-2 alignment: BUY needs SMA50 > SMA200; SELL the inverse.

    Source: Stan Weinstein ("Secrets for Profiting in Bull and Bear Markets")
    Stage-2 definition; refined by Mark Minervini's SEPA into the 50/150/200
    stacking requirement. Counter-trend trades have measurably lower hit rates
    in equity swing samples.
    """
    action = s.get("action")
    if action == "HOLD" or s.get("trend_aligned") is None or s.get("trend_aligned"):
        return None
    s50, s200 = s["sma_50"], s["sma_200"]
    if action == "BUY":
        return {
            "code": "counter_trend_buy",
            "severity": "warn",
            "message": f"BUY into downtrend stack: SMA50 ({s50:.2f}) < SMA200 ({s200:.2f}). Counter-trend buys need an explicit catalyst.",
            "source": "Weinstein Stage 2 / Minervini SEPA",
        }
    return {
        "code": "counter_trend_sell",
        "severity": "warn",
        "message": f"SELL into uptrend stack: SMA50 ({s50:.2f}) > SMA200 ({s200:.2f}).",
        "source": "Weinstein Stage 2 / Minervini SEPA",
    }


def _sector_confirmation(s: Signals) -> Warning | None:
    """CANSLIM 'L' (Leader/Laggard): BUY requires sector strength.

    Source: William O'Neil, "How to Make Money in Stocks". A bullish single-name
    thesis into a sector ETF below its 50-day SMA is fighting the group.
    """
    if s.get("action") != "BUY" or s.get("sector_above_sma_50") is not False:
        return None
    return {
        "code": "weak_sector_buy",
        "severity": "warn",
        "message": f"BUY against weak sector: {s['sector_etf']} below 50-day SMA ({s['sector_pct_change_20d']}% over 20d).",
        "source": "CANSLIM 'L' (O'Neil)",
    }


def _market_confirmation(s: Signals) -> Warning | None:
    """CANSLIM 'M' (Market direction): ~75% of stocks track the market.

    Source: William O'Neil, "How to Make Money in Stocks". Initiating longs
    when SPY is below its 50-day SMA fights the broader tape.
    """
    if s.get("action") != "BUY" or s.get("spy_above_sma_50") is not False:
        return None
    return {
        "code": "weak_market_buy",
        "severity": "warn",
        "message": f"BUY against weak market: SPY below 50-day SMA ({s['spy_pct_change_20d']}% over 20d).",
        "source": "CANSLIM 'M' (O'Neil)",
    }


def _rsi_extreme(s: Signals) -> Warning | None:
    """RSI(14) extremes: BUY at >70 (overbought) or SELL at <30 (oversold).

    Source: J. Welles Wilder Jr., "New Concepts in Technical Trading Systems"
    (1978). Strong trends sustain RSI extremes — this is INFO-level, not a
    block.
    """
    action = s.get("action")
    rsi = s.get("rsi_14")
    if action == "HOLD" or rsi is None:
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


def _macd_against_action(s: Signals) -> Warning | None:
    """MACD histogram sign disagrees with the action.

    Source: Gerald Appel, MACD (1979). The histogram (MACD - signal) is the
    short-term momentum gauge; negative-into-BUY means calling a bottom
    before momentum has confirmed.
    """
    action = s.get("action")
    if action == "HOLD" or s.get("macd_aligned") is None or s.get("macd_aligned"):
        return None
    hist = s["macd_hist"]
    if action == "BUY":
        return {
            "code": "macd_bearish_buy",
            "severity": "warn",
            "message": f"BUY with MACD histogram negative ({hist:.3f}). Momentum has not yet turned up.",
            "source": "MACD (Appel)",
        }
    return {
        "code": "macd_bullish_sell",
        "severity": "warn",
        "message": f"SELL with MACD histogram positive ({hist:.3f}). Momentum has not yet turned down.",
        "source": "MACD (Appel)",
    }


def _extended_from_sma50(s: Signals) -> Warning | None:
    """Price >10% above SMA50: Minervini's "extended" zone — chase-buyer trap.

    Source: Mark Minervini, "Trade Like a Stock Market Wizard". SEPA explicitly
    warns against initiating new positions when extended; sweet spot is
    within ~5% of a rising 50-day.
    """
    if s.get("action") != "BUY" or not s.get("extended"):
        return None
    ext = s["pct_above_sma_50"]
    return {
        "code": "extended_from_sma50",
        "severity": "warn",
        "message": f"Price {ext:.1f}% above SMA50. Minervini's 'extended' zone — chase-buyer entries historically underperform.",
        "source": "Minervini SEPA",
    }


def _risk_reward(s: Signals) -> Warning | None:
    """Reward-to-risk ratio < 1.5:1 from the deterministic S/R.

    Source: Van Tharp, "Trade Your Way to Financial Freedom"; standard
    position-sizing literature. Pros target >=2:1; <1.5:1 is the threshold
    where expectancy turns negative for typical win rates (45-55%).
    """
    action = s.get("action")
    ratio = s.get("reward_risk_ratio")
    if action == "HOLD" or ratio is None or ratio >= 1.5:
        return None
    return {
        "code": f"poor_rr_{action.lower()}",
        "severity": "warn",
        "message": f"Reward:risk = {ratio:.2f}:1 from deterministic levels. Pros require >= 2:1 (Van Tharp).",
        "source": "Van Tharp position sizing",
    }


def _earnings_window(s: Signals) -> Warning | None:
    """Initiating positions inside the 0-5 day pre-earnings window.

    Source: institutional swing convention (Minervini, Dan Zanger, etc.).
    Pre-earnings trades are event-driven — a clean technical setup does not
    survive the print. Acceptable only when the earnings reaction IS the
    thesis.
    """
    action = s.get("action")
    dte = s.get("days_until_earnings")
    if action == "HOLD" or dte is None or not (0 <= dte <= 5):
        return None
    return {
        "code": "inside_earnings_window",
        "severity": "strong",
        "message": f"{action} with earnings in {dte} day(s). Pre-earnings is a coin-flip unless the earnings reaction IS the thesis.",
        "source": "Minervini / institutional swing convention",
    }


def _volume_confirmation(s: Signals) -> Warning | None:
    """BUY on volume meaningfully below the 20-day average.

    Source: Dow Theory volume principle; codified by O'Neil/IBD. Conviction-
    light entries (especially at/near highs) are statistically more likely
    to fail and get retraced.
    """
    ratio = s.get("volume_ratio")
    if s.get("action") != "BUY" or ratio is None or ratio >= 0.7:
        return None
    return {
        "code": "low_volume_buy",
        "severity": "info",
        "message": f"BUY with current volume {ratio:.0%} of 20-day average. Light-volume entries get retraced.",
        "source": "Dow Theory / IBD volume confirmation",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def validate_verdict(
    payload: dict[str, Any],
    facts: dict[str, Any],
) -> list[Warning]:
    """Run every check against the shared signals; return non-None warnings."""
    s = compute_signals(payload, facts)
    results: list[Warning | None] = [
        _trend_stack_aligned(s),
        _sector_confirmation(s),
        _market_confirmation(s),
        _rsi_extreme(s),
        _macd_against_action(s),
        _extended_from_sma50(s),
        _risk_reward(s),
        _earnings_window(s),
        _volume_confirmation(s),
    ]
    return [w for w in results if w is not None]
