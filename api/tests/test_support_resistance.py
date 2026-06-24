"""`tools.support_resistance.find_support_resistance` — pivot + cluster logic.

A constructed series with two equal swing highs and two equal swing lows must
cluster into one resistance (above last close) and one support (below it), with
the touch counts and rounded prices we expect. Pure pandas, no I/O.
"""

import pandas as pd

from bull_api.tools.support_resistance import find_support_resistance


def _frame(highs, lows, closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"High": highs, "Low": lows, "Close": closes}, index=idx)


def test_too_few_rows_returns_empty():
    df = _frame([100] * 5, [99] * 5, [100] * 5)
    assert find_support_resistance(df) == {"support": [], "resistance": []}


def test_double_top_and_double_bottom_cluster():
    n = 30
    highs = [100.0] * n
    lows = [95.0] * n
    closes = [100.0] * n
    # Two equal swing highs at 110 (resistance) and two equal swing lows at 90
    # (support); flat elsewhere so no spurious pivots form.
    highs[10] = highs[20] = 110.0
    lows[12] = lows[22] = 90.0
    sr = find_support_resistance(_frame(highs, lows, closes))

    assert len(sr["resistance"]) == 1
    res = sr["resistance"][0]
    assert res["price"] == 110.0
    assert res["touch_count"] == 2
    assert res["last_touch_date"] == "2024-01-21"  # later of the two highs (idx 20)

    assert len(sr["support"]) == 1
    sup = sr["support"][0]
    assert sup["price"] == 90.0
    assert sup["touch_count"] == 2
    assert sup["last_touch_date"] == "2024-01-23"  # later of the two lows (idx 22)


def test_levels_split_around_current_price():
    n = 30
    highs = [100.0] * n
    lows = [95.0] * n
    closes = [100.0] * n
    highs[10] = highs[20] = 110.0
    lows[12] = lows[22] = 90.0
    sr = find_support_resistance(_frame(highs, lows, closes))
    last_close = closes[-1]
    assert all(lvl["price"] >= last_close for lvl in sr["resistance"])
    assert all(lvl["price"] < last_close for lvl in sr["support"])
    assert len(sr["support"]) <= 3 and len(sr["resistance"]) <= 3
