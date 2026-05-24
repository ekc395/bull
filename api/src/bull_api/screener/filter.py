"""Strict 5-conjunction technical screen.

Tuned for swing-trading BUY candidates:
- RSI 30-55: not overbought, but past the deepest oversold spike (avoids knife-catching)
- MACD histogram > 0: momentum has turned up
- close > SMA-50: above medium-term trend
- SMA-50 > SMA-200: golden-cross regime (long-term trend up)
- volume > 20d average: participation confirms the move

Any missing indicator (e.g. an IPO < 200 trading days old has no SMA-200) fails
the screen by design.
"""

from ..tools.indicators import IndicatorSnapshot


def passes_strict_filter(snap: IndicatorSnapshot, close: float) -> bool:
    rsi = snap.get("rsi_14")
    macd_hist = snap.get("macd_hist")
    sma_50 = snap.get("sma_50")
    sma_200 = snap.get("sma_200")
    vol_now = snap.get("volume_current")
    vol_avg = snap.get("volume_20d_avg")

    if None in (rsi, macd_hist, sma_50, sma_200, vol_now, vol_avg):
        return False

    return (
        30.0 <= rsi <= 55.0  # type: ignore[operator]
        and macd_hist > 0.0  # type: ignore[operator]
        and close > sma_50  # type: ignore[operator]
        and sma_50 > sma_200  # type: ignore[operator]
        and vol_now > vol_avg  # type: ignore[operator]
    )
