"""yfinance OHLCV fetch with per-(ticker, date) in-memory cache."""

import pandas as pd


def get_price_history(ticker: str, lookback_days: int = 270) -> pd.DataFrame:
    """Daily OHLCV DataFrame for `ticker` over the last `lookback_days`."""
    raise NotImplementedError
