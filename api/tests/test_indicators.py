"""`tools.indicators.compute_indicators` — the indicator math.

Closes the biggest math-coverage hole: known OHLCV in → known SMA/ATR/MACD,
RSI bounds, and degenerate-series None handling. Pure pandas, no I/O.
"""

import pandas as pd
import pytest

from bull_api.tools.indicators import compute_indicators


def _frame(highs, lows, closes, vols=None):
    n = len(closes)
    vols = vols if vols is not None else [1000] * n
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"High": highs, "Low": lows, "Close": closes, "Volume": vols}, index=idx
    )


def test_constant_series_smas_and_atr():
    # Flat 100 close, 99/101 range → SMA flat, TR is a constant 2, no drift.
    n = 250
    df = _frame([101.0] * n, [99.0] * n, [100.0] * n)
    snap = compute_indicators(df)
    assert snap["sma_20"] == pytest.approx(100.0)
    assert snap["sma_50"] == pytest.approx(100.0)
    assert snap["sma_200"] == pytest.approx(100.0)
    assert snap["atr_14"] == pytest.approx(2.0)
    assert snap["volume_current"] == pytest.approx(1000.0)
    assert snap["volume_20d_avg"] == pytest.approx(1000.0)
    # No price movement → MACD components collapse to zero.
    assert snap["macd"] == pytest.approx(0.0)
    assert snap["macd_signal"] == pytest.approx(0.0)
    assert snap["macd_hist"] == pytest.approx(0.0)
    # No down days → avg_loss is 0 → RSI is undefined → None.
    assert snap["rsi_14"] is None


def test_ramp_series_sma_and_atr_exact():
    n = 250
    closes = [float(i) for i in range(1, n + 1)]
    df = _frame([c + 0.5 for c in closes], [c - 0.5 for c in closes], closes)
    snap = compute_indicators(df)
    # mean of the trailing window of a 1..n ramp.
    assert snap["sma_20"] == pytest.approx(240.5)  # mean(231..250)
    assert snap["sma_50"] == pytest.approx(225.5)  # mean(201..250)
    assert snap["sma_200"] == pytest.approx(150.5)  # mean(51..250)
    # Daily TR settles at 1.5 (|high-prev_close| dominates the 1.0 high-low).
    assert snap["atr_14"] == pytest.approx(1.5)


def test_short_series_returns_none_for_unwarmed_smas():
    closes = [100, 101, 100, 102, 101, 103, 102, 104, 103, 105]
    df = _frame([c + 0.5 for c in closes], [c - 0.5 for c in closes], closes)
    snap = compute_indicators(df)
    assert snap["sma_20"] is None
    assert snap["sma_50"] is None
    assert snap["sma_200"] is None
    # The latest-bar fields that don't need a long window still resolve.
    assert snap["volume_current"] == pytest.approx(1000.0)


def test_rsi_within_bounds_on_mixed_series():
    n = 60
    closes = [100.0 + (i % 2) for i in range(n)]  # alternating up/down days
    df = _frame([c + 0.5 for c in closes], [c - 0.5 for c in closes], closes)
    snap = compute_indicators(df)
    assert 0.0 < snap["rsi_14"] < 100.0
    assert 0.0 < snap["rsi_2"] < 100.0
