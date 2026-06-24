"""`scoring._find_entry_index` + `_classify_hit` — pure scoring helpers.

`_find_entry_index` must return a scalar int even on a non-unique DatetimeIndex
(a duplicate yfinance timestamp) — the searchsorted fix. `_classify_hit`
encodes the BUY/SELL/HOLD hit conventions.
"""

from datetime import date

import pandas as pd

from bull_api.scoring import _classify_hit, _find_entry_index


def _df(dates, closes=None):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    closes = closes if closes is not None else list(range(len(dates)))
    return pd.DataFrame({"Close": closes}, index=idx)


# --- _find_entry_index -----------------------------------------------------


def test_find_entry_index_exact_date():
    df = _df(["2024-01-02", "2024-01-03", "2024-01-04"])
    assert _find_entry_index(df, date(2024, 1, 3)) == 1


def test_find_entry_index_skips_weekend_to_next_session():
    # Fri / Mon / Tue bars; a Saturday verdict scores from Monday's close.
    df = _df(["2024-01-05", "2024-01-08", "2024-01-09"])
    assert _find_entry_index(df, date(2024, 1, 6)) == 1


def test_find_entry_index_handles_duplicate_timestamps():
    # Duplicate index → get_loc would return a slice (TypeError); searchsorted
    # returns the leftmost scalar position.
    df = _df(["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-03"])
    assert _find_entry_index(df, date(2024, 1, 2)) == 1


def test_find_entry_index_none_when_no_future_row():
    df = _df(["2024-01-01", "2024-01-02"])
    assert _find_entry_index(df, date(2024, 1, 5)) is None


# --- _classify_hit ---------------------------------------------------------


def test_classify_hit_buy():
    assert _classify_hit("BUY", 5.0, 0.0) is True
    assert _classify_hit("BUY", -1.0, 0.0) is False
    # Threshold raises the bar a BUY must clear.
    assert _classify_hit("BUY", 1.0, 2.0) is False


def test_classify_hit_sell_inverts_sign():
    assert _classify_hit("SELL", -5.0, 0.0) is True
    assert _classify_hit("SELL", 5.0, 0.0) is False
    assert _classify_hit("SELL", -1.0, 2.0) is False


def test_classify_hit_hold_uses_no_move_band():
    # band = max(threshold, 1.0)
    assert _classify_hit("HOLD", 0.5, 0.0) is True
    assert _classify_hit("HOLD", 2.0, 0.0) is False
    assert _classify_hit("HOLD", 2.5, 3.0) is True  # wider band from threshold


def test_classify_hit_unknown_action_is_none():
    assert _classify_hit("WAIT", 5.0, 0.0) is None
