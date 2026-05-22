"""Macro + sector context. Per-(sector_etf, trading-day) in-memory cache.

A swing-trade verdict that ignores the broader tape is unreliable: NVDA
doesn't trade in a vacuum, it tracks SOXX; a "bullish" semis chart into a
rolling-over SOXX is a different bet than the same chart with SOXX trending up.

Returns trend snapshots for SPY (market), a sector ETF mapped from the ticker's
sector/industry, and VIX (volatility regime). All fields are best-effort —
yfinance failures degrade to None rather than killing the analysis.
"""

import time
from typing import TypedDict

import yfinance as yf

from ..time import trading_day


class TrendSnapshot(TypedDict):
    symbol: str
    last_close: float | None
    pct_change_20d: float | None
    pct_change_50d: float | None
    above_sma_50: bool | None
    above_sma_200: bool | None


class MarketContext(TypedDict):
    spy: TrendSnapshot
    sector_etf: str | None  # e.g. "XLK", "SOXX"
    sector: TrendSnapshot | None
    vix_level: float | None
    # "calm" <15, "normal" 15-20, "elevated" 20-25, "high" >25
    vix_state: str | None


# yfinance `.info["sector"]` taxonomy → SPDR sector ETF.
SECTOR_ETF: dict[str, str] = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

# Narrower industry ETFs that track better than the broad sector for these groups.
# Match by substring against yfinance's `industry` string.
INDUSTRY_ETF_KEYWORDS: list[tuple[str, str]] = [
    ("semiconductor", "SOXX"),
    ("biotechnology", "XBI"),
    ("regional bank", "KRE"),
    ("oil & gas e&p", "XOP"),
    ("oil & gas drill", "XOP"),
    ("homebuild", "XHB"),
    ("airline", "JETS"),
    ("gold", "GDX"),
    ("aerospace", "ITA"),
    ("retail", "XRT"),
]

_TTL_SECONDS = 6 * 60 * 60  # 6h: market state moves intraday; don't cache too long.
_cache: dict[tuple[str | None, str], tuple[float, MarketContext]] = {}


def _resolve_sector_etf(sector: str | None, industry: str | None) -> str | None:
    if industry:
        low = industry.lower()
        for kw, etf in INDUSTRY_ETF_KEYWORDS:
            if kw in low:
                return etf
    if sector:
        return SECTOR_ETF.get(sector)
    return None


def _snapshot(symbol: str) -> TrendSnapshot:
    """Pull 250 calendar days for `symbol` and reduce to a trend snapshot.

    Returns a snapshot with None fields if the fetch fails — never raises.
    """
    blank: TrendSnapshot = {
        "symbol": symbol,
        "last_close": None,
        "pct_change_20d": None,
        "pct_change_50d": None,
        "above_sma_50": None,
        "above_sma_200": None,
    }
    try:
        df = yf.Ticker(symbol).history(period="250d", auto_adjust=True)
    except Exception:
        return blank
    if df is None or df.empty or "Close" not in df.columns:
        return blank

    close = df["Close"].dropna()
    if len(close) == 0:
        return blank
    last = float(close.iloc[-1])

    def _pct(lookback: int) -> float | None:
        if len(close) <= lookback:
            return None
        prior = float(close.iloc[-1 - lookback])
        return round((last / prior - 1.0) * 100.0, 2) if prior else None

    def _above_sma(window: int) -> bool | None:
        if len(close) < window:
            return None
        return last > float(close.tail(window).mean())

    return {
        "symbol": symbol,
        "last_close": round(last, 2),
        "pct_change_20d": _pct(20),
        "pct_change_50d": _pct(50),
        "above_sma_50": _above_sma(50),
        "above_sma_200": _above_sma(200),
    }


def _vix_level() -> float | None:
    try:
        df = yf.Ticker("^VIX").history(period="10d", auto_adjust=True)
    except Exception:
        return None
    if df is None or df.empty or "Close" not in df.columns:
        return None
    series = df["Close"].dropna()
    return round(float(series.iloc[-1]), 2) if len(series) else None


def _vix_state(level: float | None) -> str | None:
    if level is None:
        return None
    if level < 15:
        return "calm"
    if level < 20:
        return "normal"
    if level < 25:
        return "elevated"
    return "high"


def get_market_context(sector: str | None, industry: str | None) -> MarketContext:
    """SPY trend + sector ETF trend + VIX level/state.

    Cached for 6h per (sector_etf, trading_day) so a batch of analyses on the
    same day reuses a single SPY/VIX fetch.
    """
    sector_etf = _resolve_sector_etf(sector, industry)
    cache_key = (sector_etf, trading_day().isoformat())
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    spy = _snapshot("SPY")
    sector_snap = _snapshot(sector_etf) if sector_etf else None
    vix = _vix_level()
    result: MarketContext = {
        "spy": spy,
        "sector_etf": sector_etf,
        "sector": sector_snap,
        "vix_level": vix,
        "vix_state": _vix_state(vix),
    }
    _cache[cache_key] = (now, result)
    return result


if __name__ == "__main__":
    import sys

    sec = sys.argv[1] if len(sys.argv) > 1 else "Technology"
    ind = sys.argv[2] if len(sys.argv) > 2 else "Semiconductors"
    ctx = get_market_context(sec, ind)
    for k, v in ctx.items():
        print(f"{k}: {v}")
