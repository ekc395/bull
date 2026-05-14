"""Technical indicators computed via pandas rolling windows. No ta-lib dep."""

from typing import TypedDict

import pandas as pd


class IndicatorSnapshot(TypedDict):
    rsi_14: float
    macd: float
    macd_signal: float
    macd_hist: float
    sma_20: float
    sma_50: float
    sma_200: float
    ema_12: float
    ema_26: float
    atr_14: float
    volume_20d_avg: float
    volume_current: float


def compute_indicators(prices: pd.DataFrame) -> IndicatorSnapshot:
    raise NotImplementedError
