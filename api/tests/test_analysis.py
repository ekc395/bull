"""Phase 2 — calibration & edge tables.

Hand-built Outcome rows → known hit-rate / return numbers. Exercises the pure
table builders directly (no DB), the min-n thin flag, and the per-feature edge
slicing.
"""

from bull_api.config import settings
from bull_api.policy.analysis import (
    Outcome,
    _resolve_model,
    by_model_counts,
    calibration_table,
    edge_table,
)
from bull_api.policy.features import Context


def _ctx(**over) -> Context:
    base = dict(
        action="BUY",
        timeframe="short",
        confidence_band="70-84",
        reward_risk_band="2-3",
        trend_aligned=True,
        sector_above_sma_50=True,
        market_above_sma_50=True,
        vix_state="calm",
        earnings_window=False,
    )
    base.update(over)
    return Context(**base)


def _o(ret, *, horizon=5, action="BUY", **ctx_over) -> Outcome:
    return Outcome(
        context=_ctx(action=action, **ctx_over),
        action=action,
        horizon_days=horizon,
        return_pct=ret,
    )


# --- calibration -----------------------------------------------------------


def test_calibration_hit_rate_by_band():
    # BUY hits when return > 0 (threshold default 0).
    outcomes = [
        _o(5.0, confidence_band="85-100"),
        _o(3.0, confidence_band="85-100"),
        _o(-2.0, confidence_band="85-100"),  # miss
        _o(1.0, confidence_band="55-69"),
        _o(-1.0, confidence_band="55-69"),  # miss
    ]
    table = calibration_table(outcomes, min_n=1)
    high = table["5d"]["85-100"]
    low = table["5d"]["55-69"]
    assert high["n"] == 3
    assert high["hit_rate"] == round(2 / 3, 4)
    assert high["mean_return_pct"] == 2.0  # (5+3-2)/3
    assert low["n"] == 2
    assert low["hit_rate"] == 0.5
    # descending band order preserved
    assert list(table["5d"].keys()) == ["85-100", "55-69"]


def test_calibration_thin_flag():
    outcomes = [_o(1.0, confidence_band="70-84") for _ in range(3)]
    table = calibration_table(outcomes, min_n=5)
    assert table["5d"]["70-84"]["thin"] is True
    table2 = calibration_table(outcomes, min_n=3)
    assert "thin" not in table2["5d"]["70-84"]


def test_calibration_separates_horizons():
    outcomes = [_o(2.0, horizon=5), _o(-2.0, horizon=20)]
    table = calibration_table(outcomes, min_n=1)
    assert table["5d"]["70-84"]["hit_rate"] == 1.0
    assert table["20d"]["70-84"]["hit_rate"] == 0.0


def test_calibration_threshold_shifts_hits():
    outcomes = [_o(1.5), _o(0.5)]  # both positive
    assert calibration_table(outcomes, min_n=1)["5d"]["70-84"]["hit_rate"] == 1.0
    # raise the bar to 1% → only the 1.5% return counts as a hit
    hi = calibration_table(outcomes, threshold=1.0, min_n=1)
    assert hi["5d"]["70-84"]["hit_rate"] == 0.5


# --- edge ------------------------------------------------------------------


def test_edge_slices_by_trend_aligned():
    outcomes = [
        _o(4.0, trend_aligned=True),
        _o(2.0, trend_aligned=True),
        _o(-3.0, trend_aligned=False),
    ]
    table = edge_table(outcomes, min_n=1)
    trend = table["5d"]["trend_aligned"]
    assert trend["true"]["n"] == 2
    assert trend["true"]["hit_rate"] == 1.0
    assert trend["false"]["n"] == 1
    assert trend["false"]["hit_rate"] == 0.0


def test_edge_covers_every_feature():
    table = edge_table([_o(1.0)], min_n=1)
    feats = set(table["5d"].keys())
    assert feats == {
        "confidence_band",
        "reward_risk_band",
        "trend_aligned",
        "sector_above_sma_50",
        "market_above_sma_50",
        "vix_state",
        "earnings_window",
    }


def test_edge_none_and_bool_value_keys():
    outcomes = [
        _o(1.0, sector_above_sma_50=None),
        _o(-1.0, sector_above_sma_50=False),
    ]
    sector = edge_table(outcomes, min_n=1)["5d"]["sector_above_sma_50"]
    assert set(sector.keys()) == {"none", "false"}


def test_edge_empty_outcomes():
    assert edge_table([], min_n=1) == {}
    assert calibration_table([], min_n=1) == {}


# --- model regime filter ---------------------------------------------------


def test_resolve_model_selector():
    assert _resolve_model(None) is None  # default: pool every model
    assert _resolve_model("all") is None  # legacy alias for pooling
    assert _resolve_model("current") == settings.bull_model  # active regime
    assert _resolve_model("claude-x") == "claude-x"  # explicit passthrough


def test_by_model_counts_groups_and_sorts():
    outcomes = [
        Outcome(context=_ctx(), action="BUY", horizon_days=5, return_pct=1.0, model="claude-b"),
        Outcome(context=_ctx(), action="BUY", horizon_days=5, return_pct=2.0, model="claude-a"),
        Outcome(context=_ctx(), action="BUY", horizon_days=5, return_pct=3.0, model="claude-b"),
        Outcome(context=_ctx(), action="BUY", horizon_days=5, return_pct=4.0),  # no model tag
    ]
    assert by_model_counts(outcomes) == {"claude-a": 1, "claude-b": 2, "unknown": 1}
    assert by_model_counts([]) == {}
