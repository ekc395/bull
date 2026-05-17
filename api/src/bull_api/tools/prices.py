"""yfinance OHLCV fetch with per-(ticker, trading-day) in-memory cache."""

from datetime import date

import pandas as pd
import yfinance as yf

from ..time import trading_day

_cache: dict[tuple[str, int, date], pd.DataFrame] = {}


def get_price_history(ticker: str, lookback_days: int = 400) -> pd.DataFrame:
    """Daily OHLCV DataFrame for `ticker` over the last `lookback_days` calendar days.

    Columns: Open, High, Low, Close, Volume (split/dividend adjusted).
    Index: tz-naive DatetimeIndex of trading days.
    Cached per process by (ticker, lookback_days, ET trading day) — same ticker
    on the same trading session returns the cached frame without hitting yfinance.
    """
    key = (ticker.upper(), lookback_days, trading_day())
    if key in _cache:
        return _cache[key]

    df = yf.Ticker(ticker).history(period=f"{lookback_days}d", auto_adjust=True)
    if df.empty:
        raise ValueError(f"No price data returned for {ticker!r}")

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.tz_localize(None)
    _cache[key] = df
    return df


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    frame = get_price_history(symbol)
    print(f"{symbol}: {len(frame)} rows  {frame.index[0].date()} → {frame.index[-1].date()}")
    print(frame.tail(3))
