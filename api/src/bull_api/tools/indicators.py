"""Technical indicators computed via pandas rolling windows. No ta-lib dep."""

from math import isnan
from typing import TypedDict

import pandas as pd


class IndicatorSnapshot(TypedDict):
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    ema_12: float | None
    ema_26: float | None
    atr_14: float | None
    volume_20d_avg: float | None
    volume_current: float | None


def _f(x: float) -> float | None:
    return None if x is None or isnan(x) else float(x)


def _wilder(s: pd.Series, period: int) -> pd.Series:
    # Wilder's smoothing is an EMA with alpha = 1/period.
    return s.ewm(alpha=1.0 / period, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = _wilder(gain, period)
    avg_loss = _wilder(loss, period)
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return _wilder(tr, period)


def compute_indicators(prices: pd.DataFrame) -> IndicatorSnapshot:
    """Latest-bar snapshot of standard swing-trading indicators."""
    close = prices["Close"]
    high = prices["High"]
    low = prices["Low"]
    volume = prices["Volume"]

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    rsi = _rsi(close)
    atr = _atr(high, low, close)
    sma_20 = close.rolling(20).mean()
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    vol_20 = volume.rolling(20).mean()

    return {
        "rsi_14": _f(rsi.iloc[-1]),
        "macd": _f(macd.iloc[-1]),
        "macd_signal": _f(macd_signal.iloc[-1]),
        "macd_hist": _f(macd_hist.iloc[-1]),
        "sma_20": _f(sma_20.iloc[-1]),
        "sma_50": _f(sma_50.iloc[-1]),
        "sma_200": _f(sma_200.iloc[-1]),
        "ema_12": _f(ema_12.iloc[-1]),
        "ema_26": _f(ema_26.iloc[-1]),
        "atr_14": _f(atr.iloc[-1]),
        "volume_20d_avg": _f(vol_20.iloc[-1]),
        "volume_current": _f(volume.iloc[-1]),
    }


if __name__ == "__main__":
    import sys

    from .prices import get_price_history

    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    frame = get_price_history(symbol)
    snap = compute_indicators(frame)
    for key, value in snap.items():
        print(f"{key:18s} {value}")
        