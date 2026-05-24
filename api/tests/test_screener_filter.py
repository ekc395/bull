"""Strict 5-conjunction filter — each rule isolated + happy/missing paths."""

import pytest

from bull_api.screener.filter import passes_strict_filter
from bull_api.tools.indicators import IndicatorSnapshot


def _snap(**overrides) -> IndicatorSnapshot:
    base: IndicatorSnapshot = {
        "rsi_14": 45.0,
        "macd": 1.0,
        "macd_signal": 0.5,
        "macd_hist": 0.5,
        "sma_20": 100.0,
        "sma_50": 95.0,
        "sma_200": 90.0,
        "ema_12": 100.0,
        "ema_26": 99.0,
        "atr_14": 2.0,
        "volume_20d_avg": 1_000_000.0,
        "volume_current": 1_200_000.0,
    }
    base.update(overrides)
    return base


def test_happy_path_passes():
    assert passes_strict_filter(_snap(), close=100.0) is True


@pytest.mark.parametrize("rsi", [29.9, 55.1, 72.0])
def test_rsi_band_rejects(rsi):
    assert passes_strict_filter(_snap(rsi_14=rsi), close=100.0) is False


def test_macd_hist_negative_rejects():
    assert passes_strict_filter(_snap(macd_hist=-0.01), close=100.0) is False


def test_close_below_sma50_rejects():
    assert passes_strict_filter(_snap(), close=94.99) is False


def test_sma50_below_sma200_rejects():
    assert passes_strict_filter(_snap(sma_50=85.0, sma_200=90.0), close=100.0) is False


def test_volume_below_avg_rejects():
    assert passes_strict_filter(_snap(volume_current=999_999.0), close=100.0) is False


@pytest.mark.parametrize(
    "missing",
    ["rsi_14", "macd_hist", "sma_50", "sma_200", "volume_current", "volume_20d_avg"],
)
def test_missing_indicator_rejects(missing):
    snap = _snap(**{missing: None})
    assert passes_strict_filter(snap, close=100.0) is False


def test_rsi_boundaries_inclusive():
    assert passes_strict_filter(_snap(rsi_14=30.0), close=100.0) is True
    assert passes_strict_filter(_snap(rsi_14=55.0), close=100.0) is True
