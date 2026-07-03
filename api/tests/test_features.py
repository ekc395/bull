"""Phase 1 — signal extraction + bucketed context.

Synthetic facts bundles → expected signals/buckets. Asserts the R:R the policy
layer buckets on is the *same* number the warning validators use, since both
flow through `checks.compute_signals`.
"""

from types import SimpleNamespace

from bull_api.checks import _reward_risk_ratio, compute_signals, validate_verdict
from bull_api.policy.features import (
    Context,
    confidence_band,
    context_for,
    effective_reward_risk,
    reward_risk_band,
)


def _facts(**over):
    """A clean, BUY-favorable facts bundle; override pieces per test."""
    facts = {
        "prices": [{"close": 100.0}],
        "indicators": {
            "sma_50": 95.0,
            "sma_200": 90.0,
            "rsi_14": 55.0,
            "macd_hist": 0.5,
            "volume_current": 1_200_000,
            "volume_20d_avg": 1_000_000,
        },
        "support_resistance": {
            "support": [{"price": 96.0}, {"price": 92.0}],
            "resistance": [{"price": 110.0}, {"price": 120.0}],
        },
        "market_context": {
            "spy": {"above_sma_50": True, "pct_change_20d": 2.0},
            "sector_etf": "XLK",
            "sector": {"above_sma_50": True, "pct_change_20d": 3.0},
            "vix_level": 13.0,
            "vix_state": "calm",
        },
        "fundamentals": {"days_until_earnings": 40},
    }
    facts.update(over)
    return facts


# --- compute_signals -------------------------------------------------------


def test_signals_direction_aware_for_buy():
    s = compute_signals({"action": "BUY"}, _facts())
    assert s["trend_stack_up"] is True
    assert s["trend_aligned"] is True  # BUY agrees with up-stack
    assert s["macd_aligned"] is True  # hist >= 0
    # last=100, nearest support=96 (risk 4), furthest resistance=120 (reward 20)
    assert s["reward_risk_ratio"] == 5.0
    assert s["volume_ratio"] == 1.2
    assert abs(s["pct_above_sma_50"] - (100 / 95 - 1) * 100) < 1e-9
    assert s["extended"] is False


def test_signals_direction_aware_for_sell():
    # Down-stack so SELL is trend-aligned; last between support and resistance.
    facts = _facts(
        indicators={"sma_50": 90.0, "sma_200": 95.0, "macd_hist": -0.4},
        support_resistance={
            "support": [{"price": 80.0}],
            "resistance": [{"price": 104.0}],
        },
    )
    s = compute_signals({"action": "SELL"}, facts)
    assert s["trend_stack_up"] is False
    assert s["trend_aligned"] is True  # SELL agrees with down-stack
    assert s["macd_aligned"] is True  # hist <= 0 for SELL
    # SELL: risk = 104-100 = 4, reward = 100-80 = 20
    assert s["reward_risk_ratio"] == 5.0


def test_signals_none_tolerant_on_empty_bundle():
    s = compute_signals({"action": "BUY"}, {})
    assert s["trend_aligned"] is None
    assert s["reward_risk_ratio"] is None
    assert s["volume_ratio"] is None
    assert s["pct_above_sma_50"] is None
    assert s["vix_state"] is None


def test_hold_has_no_directional_alignment():
    s = compute_signals({"action": "HOLD"}, _facts())
    assert s["trend_aligned"] is None
    assert s["macd_aligned"] is None
    assert s["reward_risk_ratio"] is None  # R:R only defined for BUY/SELL


def test_rr_matches_shared_helper():
    facts = _facts()
    s = compute_signals({"action": "BUY"}, facts)
    assert s["reward_risk_ratio"] == _reward_risk_ratio("BUY", facts)


# --- validators still fire from the shared signals -------------------------


def test_counter_trend_buy_warns():
    facts = _facts(indicators={"sma_50": 90.0, "sma_200": 95.0, "macd_hist": 0.1})
    codes = {w["code"] for w in validate_verdict({"action": "BUY"}, facts)}
    assert "counter_trend_buy" in codes


def test_clean_buy_has_no_warnings():
    assert validate_verdict({"action": "BUY"}, _facts()) == []


def test_earnings_window_strong_warning():
    facts = _facts(fundamentals={"days_until_earnings": 2})
    warnings = validate_verdict({"action": "BUY"}, facts)
    earn = [w for w in warnings if w["code"] == "inside_earnings_window"]
    assert earn and earn[0]["severity"] == "strong"


# --- bucketing -------------------------------------------------------------


def test_confidence_bands():
    assert confidence_band(90) == "85-100"
    assert confidence_band(84) == "70-84"
    assert confidence_band(55) == "55-69"
    assert confidence_band(40) == "40-54"
    assert confidence_band(10) == "0-39"
    assert confidence_band(None) is None


def test_reward_risk_bands():
    assert reward_risk_band(None) == "na"
    assert reward_risk_band(0.5) == "<1"
    assert reward_risk_band(1.4) == "1-2"
    assert reward_risk_band(2.5) == "2-3"
    assert reward_risk_band(5.0) == ">=3"


# --- context_for -----------------------------------------------------------


def _verdict(action="BUY", confidence=78, timeframe="short", facts=None):
    return SimpleNamespace(
        action=action,
        confidence=confidence,
        timeframe=timeframe,
        facts_bundle_json=_facts() if facts is None else facts,
    )


def _algo_verdict(rr, active="turtle-20-v1", facts=None):
    return SimpleNamespace(
        action="BUY",
        confidence=65,
        timeframe="short",
        facts_bundle_json=_facts() if facts is None else facts,
        algo_json={"active_strategy": active, "evaluations": {active: {"reward_risk": rr}}},
    )


# --- effective_reward_risk: gate/bucket the trade actually placed -----------


def test_effective_rr_prefers_strategy_bracket():
    # S/R geometry here is a fat 5.0, but the strategy's own ATR bracket is 2.0.
    assert effective_reward_risk(_algo_verdict(2.0)) == 2.0


def test_effective_rr_uses_strategy_when_sr_is_na():
    # Breakout at the top of the range: no resistance above → S/R R:R is None,
    # yet the turtle bracket is a clean 2.0 (this is the case that was rejecting).
    facts = _facts(support_resistance={"support": [{"price": 90.0}], "resistance": []})
    assert _reward_risk_ratio("BUY", facts) is None
    assert effective_reward_risk(_algo_verdict(2.0, facts=facts)) == 2.0


def test_effective_rr_falls_back_to_sr_for_non_algo():
    assert effective_reward_risk(_verdict()) == 5.0  # no algo_json → S/R ratio


def test_context_for_algo_buckets_on_strategy_rr():
    # S/R R:R is 5.0 (">=3"), but the bracket is 1.8 → bucket on the bracket.
    assert context_for(_algo_verdict(1.8)).reward_risk_band == "1-2"


def test_context_for_clean_buy():
    ctx = context_for(_verdict())
    assert ctx == Context(
        action="BUY",
        timeframe="short",
        confidence_band="70-84",
        reward_risk_band=">=3",
        trend_aligned=True,
        sector_above_sma_50=True,
        market_above_sma_50=True,
        vix_state="calm",
        earnings_window=False,
    )


def test_context_for_earnings_window_flag():
    v = _verdict(facts=_facts(fundamentals={"days_until_earnings": 3}))
    assert context_for(v).earnings_window is True


def test_context_for_thin_bundle_preserves_none():
    v = _verdict(confidence=None, facts={})
    ctx = context_for(v)
    assert ctx.confidence_band is None
    assert ctx.reward_risk_band == "na"
    assert ctx.trend_aligned is None
    assert ctx.vix_state is None
    assert ctx.earnings_window is False


def test_bucket_key_is_hashable_and_stable():
    key = context_for(_verdict()).bucket_key()
    assert isinstance(key, tuple)
    assert {key: 1}  # hashable
    assert key == context_for(_verdict()).bucket_key()
