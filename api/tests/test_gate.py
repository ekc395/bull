"""Phase 3 — gating & sizing.

Pure `decide` / `fit_stats` over hand-built contexts and bucket stats: guardrail
rejections, the cold-start / explore / exploit regimes, and the sizing cap.
"""

from bull_api.policy.analysis import Outcome
from bull_api.policy.features import Context
from bull_api.policy.gate import (
    CONF_FLOOR,
    MAX_SIZE_PCT,
    MIN_SAMPLES,
    RR_FLOOR,
    SIZING_HORIZON,
    BucketStats,
    decide,
    fit_stats,
)

BASE = 2.0


def _ctx(**over) -> Context:
    base = dict(
        action="BUY",
        timeframe="medium",
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


def _decide(ctx, stats, *, confidence=75, rr=2.5):
    return decide(ctx, stats, confidence=confidence, reward_risk_ratio=rr, base_size_pct=BASE)


_COLD = BucketStats(0, None, None, SIZING_HORIZON)


# --- guardrails ------------------------------------------------------------


def test_reject_hold():
    d = _decide(_ctx(action="HOLD"), _COLD)
    assert d.act is False and d.size_pct == 0.0
    assert "no-trade" in d.rationale


def test_reject_low_confidence():
    d = _decide(_ctx(), _COLD, confidence=CONF_FLOOR - 1)
    assert d.act is False
    assert "confidence" in d.rationale


def test_reject_low_reward_risk():
    d = _decide(_ctx(), _COLD, rr=RR_FLOOR - 0.1)
    assert d.act is False
    assert "reward:risk" in d.rationale


def test_reject_missing_reward_risk():
    d = _decide(_ctx(), _COLD, rr=None)
    assert d.act is False


def test_reject_earnings_window():
    d = _decide(_ctx(earnings_window=True), _COLD)
    assert d.act is False
    assert "earnings" in d.rationale


# --- regimes ---------------------------------------------------------------


def test_cold_start_acts_at_base():
    d = _decide(_ctx(), _COLD)
    assert d.act is True
    assert d.size_pct == BASE
    assert "cold-start" in d.rationale


def test_explore_acts_small():
    stats = BucketStats(MIN_SAMPLES - 1, 1.0, 0.6, SIZING_HORIZON)
    d = _decide(_ctx(), stats)
    assert d.act is True
    assert d.size_pct == BASE * 0.5
    assert "explore" in d.rationale


def test_exploit_positive_edge_scales_up():
    stats = BucketStats(MIN_SAMPLES, 3.0, 0.7, SIZING_HORIZON)
    d = _decide(_ctx(), stats, confidence=85)
    assert d.act is True
    assert d.size_pct > BASE  # scaled up by edge & confidence
    assert d.size_pct <= MAX_SIZE_PCT
    assert "exploit" in d.rationale


def test_exploit_negative_edge_rejects():
    stats = BucketStats(MIN_SAMPLES, -1.5, 0.3, SIZING_HORIZON)
    d = _decide(_ctx(), stats)
    assert d.act is False
    assert "edge" in d.rationale


def test_exploit_size_capped():
    # Huge edge + max confidence must not exceed the hard cap, even on a big base.
    stats = BucketStats(50, 100.0, 0.9, SIZING_HORIZON)
    d = decide(_ctx(), stats, confidence=100, reward_risk_ratio=5.0, base_size_pct=4.0)
    assert d.size_pct == MAX_SIZE_PCT


# --- fit_stats -------------------------------------------------------------


def _o(ret, *, action="BUY", band="70-84", horizon=SIZING_HORIZON) -> Outcome:
    return Outcome(
        context=_ctx(action=action, confidence_band=band),
        action=action,
        horizon_days=horizon,
        return_pct=ret,
    )


def test_fit_stats_matches_action_and_band():
    outcomes = [
        _o(4.0),
        _o(-2.0),
        _o(3.0, band="55-69"),  # different band — excluded
        _o(5.0, action="SELL"),  # different action — excluded
        _o(9.0, horizon=5),  # different horizon — excluded
    ]
    stats = fit_stats(outcomes, _ctx(confidence_band="70-84"))
    assert stats.n == 2
    assert stats.mean_favorable_return_pct == 1.0  # (4 + -2)/2 for BUY


def test_fit_stats_sell_favorable_is_negated():
    # A SELL that preceded a -3% move is a 3% favorable outcome.
    outcomes = [_o(-3.0, action="SELL"), _o(-1.0, action="SELL")]
    stats = fit_stats(outcomes, _ctx(action="SELL"))
    assert stats.n == 2
    assert stats.mean_favorable_return_pct == 2.0  # (3 + 1)/2


def test_fit_stats_empty_is_cold_start():
    stats = fit_stats([], _ctx())
    assert stats.n == 0
    assert stats.mean_favorable_return_pct is None
