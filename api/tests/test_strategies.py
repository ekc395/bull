"""Strategy framework: regime filters, the entry rules, LLM-review
enforcement. Synthetic facts bundles, same pattern as test_gate.py."""

from bull_api.strategy import REGISTRY, connors, enforce_llm_review, pullback, turtle
from bull_api.strategy.base import (
    HOLD_BASE_CONFIDENCE,
    LLM_SHADE_BAND,
    StrategyDecision,
)


def bundle(**over) -> dict:
    """A facts bundle that fully passes pullback-v1. Tests mutate from here."""
    facts = {
        "ticker": "TEST",
        "prices": [{"date": "2026-06-08", "close": 100.0, "volume": 1_500_000}],
        "indicators": {
            "rsi_14": 45.0,
            "macd_hist": 0.5,
            "sma_50": 96.0,  # +4.2% extension — inside every cap
            "sma_200": 90.0,  # stack up
            "volume_current": 1_500_000,
            "volume_20d_avg": 1_000_000,
        },
        "support_resistance": {
            "support": [{"price": 98.0, "touch_count": 3, "last_touch_date": "2026-06-01"}],
            "resistance": [{"price": 106.0, "touch_count": 2, "last_touch_date": "2026-05-15"}],
        },
        "fundamentals": {"days_until_earnings": 30},
        "market_context": {
            "spy": {"above_sma_50": True},
            "sector_etf": "XLK",
            "sector": {"above_sma_50": True},
            "vix_level": 14.0,
            "vix_state": "calm",
        },
    }
    facts.update(over)
    return facts


def hold_with(decision: StrategyDecision, failed: str) -> None:
    assert decision.candidate_action == "HOLD"
    assert decision.base_confidence == HOLD_BASE_CONFIDENCE
    assert failed in decision.reason


# --- registry -----------------------------------------------------------------


def test_registry_contents():
    # bounce-v1, breakout-v1 and wyckoff-spring-v1 were pruned after the
    # 2026-06 Dow-30 regime-split tournament (see plan.md / git history).
    assert list(REGISTRY) == ["pullback-v1", "connors-rsi2-v1", "turtle-20-v1"]


# --- shared regime filters (exercised through pullback) -------------------------


def test_filter_trend_stack_down():
    facts = bundle()
    facts["indicators"]["sma_200"] = 97.0  # SMA50 (96) < SMA200
    hold_with(pullback.evaluate(facts), "trend_stack_up")


def test_filter_trend_none_fails_closed():
    facts = bundle()
    facts["indicators"]["sma_200"] = None
    hold_with(pullback.evaluate(facts), "trend_stack_up")


def test_filter_weak_market():
    facts = bundle()
    facts["market_context"]["spy"]["above_sma_50"] = False
    hold_with(pullback.evaluate(facts), "market_above_sma_50")


def test_filter_weak_sector():
    facts = bundle()
    facts["market_context"]["sector"]["above_sma_50"] = None  # fail-closed
    hold_with(pullback.evaluate(facts), "sector_above_sma_50")


def test_filter_vix_high():
    facts = bundle()
    facts["market_context"]["vix_state"] = "high"
    hold_with(pullback.evaluate(facts), "vix_not_high")


def test_filter_earnings_window():
    facts = bundle()
    facts["fundamentals"]["days_until_earnings"] = 3
    hold_with(pullback.evaluate(facts), "outside_earnings_window")


def test_filter_earnings_unknown_fails_open():
    facts = bundle()
    facts["fundamentals"]["days_until_earnings"] = None
    assert pullback.evaluate(facts).candidate_action == "BUY"


def test_filter_earnings_just_reported_passes():
    facts = bundle()
    facts["fundamentals"]["days_until_earnings"] = -2
    assert pullback.evaluate(facts).candidate_action == "BUY"


# --- pullback-v1 ----------------------------------------------------------------


def test_pullback_full_pass():
    d = pullback.evaluate(bundle())
    assert d.candidate_action == "BUY"
    # 60 + RR>=3 (3.0) + MACD>=0 + 3 touches + VIX calm = 80 (also the cap)
    assert d.base_confidence == 80
    assert (d.entry, d.stop, d.target) == (100.0, 98.0, 106.0)
    assert d.reward_risk == 3.0
    assert all(c["passed"] for c in d.filters.values())
    assert all(c["passed"] for c in d.setup.values())


def test_pullback_bonuses_drop_without_extras():
    facts = bundle()
    # rr = (104.8-100)/(100-98) = 2.4 (no RR bonus), MACD negative, 2 touches,
    # VIX normal → bare 60.
    facts["support_resistance"]["resistance"][0]["price"] = 104.8
    facts["support_resistance"]["support"][0]["touch_count"] = 2
    facts["indicators"]["macd_hist"] = -0.2
    facts["market_context"]["vix_state"] = "normal"
    d = pullback.evaluate(facts)
    assert d.candidate_action == "BUY"
    assert d.base_confidence == 60


def test_pullback_far_from_support():
    facts = bundle()
    facts["support_resistance"]["support"][0]["price"] = 90.0  # 11.1% below
    hold_with(pullback.evaluate(facts), "near_support")


def test_pullback_extended():
    facts = bundle()
    facts["indicators"]["sma_50"] = 85.0  # +17.6% above SMA-50
    facts["indicators"]["sma_200"] = 80.0  # keep the stack up
    hold_with(pullback.evaluate(facts), "not_extended")


def test_pullback_rsi_not_cooled():
    facts = bundle()
    facts["indicators"]["rsi_14"] = 62.0
    hold_with(pullback.evaluate(facts), "rsi_pullback")


def test_pullback_poor_reward_risk():
    facts = bundle()
    facts["support_resistance"]["resistance"][0]["price"] = 102.0  # 1:1
    hold_with(pullback.evaluate(facts), "reward_risk")


def test_pullback_no_resistance_cannot_price_target():
    facts = bundle()
    facts["support_resistance"]["resistance"] = []  # all-time-high blindness
    hold_with(pullback.evaluate(facts), "reward_risk")


def test_pullback_empty_facts_holds():
    d = pullback.evaluate({"prices": []})
    assert d.candidate_action == "HOLD"


# --- connors-rsi2-v1 ----------------------------------------------------------------


def connors_bundle() -> dict:
    facts = bundle()
    facts["indicators"]["rsi_2"] = 6.0
    facts["indicators"]["atr_14"] = 2.0
    return facts


def test_connors_full_pass():
    d = connors.evaluate(connors_bundle())
    assert d.candidate_action == "BUY"
    # 60 + VIX calm; RSI(2) 6 is not < 5, so no deep bonus = 65
    assert d.base_confidence == 65
    assert d.stop == 100.0 - 2.5 * 2.0
    assert d.target == 100.0 + 1.0 * 2.0
    assert d.max_hold_trading_days == 5  # fast mean reversion, not the 20-bar default


def test_connors_deep_oversold_bonus():
    facts = connors_bundle()
    facts["indicators"]["rsi_2"] = 2.5
    assert connors.evaluate(facts).base_confidence == 70


def test_connors_rsi2_not_oversold():
    facts = connors_bundle()
    facts["indicators"]["rsi_2"] = 25.0
    hold_with(connors.evaluate(facts), "rsi2_oversold")


def test_connors_below_sma200():
    facts = connors_bundle()
    facts["indicators"]["sma_200"] = 101.0  # close 100 below the 200-day
    facts["indicators"]["sma_50"] = 102.0  # keep the stack up so SETUP fails
    hold_with(connors.evaluate(facts), "above_sma_200")


def test_connors_missing_atr():
    facts = connors_bundle()
    facts["indicators"]["atr_14"] = None
    hold_with(connors.evaluate(facts), "atr_known")


# --- turtle-20-v1 ---------------------------------------------------------------------


def turtle_bundle() -> dict:
    bars = [
        {"date": f"2026-05-{i:02d}", "high": 99.0, "low": 96.0, "close": 98.0, "volume": 1_000_000}
        for i in range(1, 26)
    ]
    bars.append(
        {"date": "2026-06-08", "high": 100.5, "low": 99.0, "close": 100.0, "volume": 1_500_000}
    )
    facts = bundle(prices=bars)
    facts["indicators"]["atr_14"] = 2.0
    return facts


def test_turtle_breakout_full_pass():
    d = turtle.evaluate(turtle_bundle())
    assert d.candidate_action == "BUY"
    # 60 + MACD>0 + VIX calm = 70
    assert d.base_confidence == 70
    assert d.stop == 100.0 - 4.0  # 2N below entry
    assert d.target == 100.0 + 8.0  # 2R
    assert d.reward_risk == 2.0


def test_turtle_not_a_breakout():
    facts = turtle_bundle()
    facts["prices"][-1]["close"] = 98.5  # below the prior 20-bar high of 99
    hold_with(turtle.evaluate(facts), "donchian_20_breakout")


def test_turtle_insufficient_history():
    facts = turtle_bundle()
    facts["prices"] = facts["prices"][-10:]
    hold_with(turtle.evaluate(facts), "donchian_20_breakout")


def test_turtle_missing_atr():
    facts = turtle_bundle()
    facts["indicators"]["atr_14"] = None
    hold_with(turtle.evaluate(facts), "atr_known")


# --- enforce_llm_review ------------------------------------------------------------


def buy_decision(base: int = 70) -> StrategyDecision:
    return StrategyDecision(
        strategy="pullback-v1",
        candidate_action="BUY",
        base_confidence=base,
        reason="test",
        filters={},
        setup={},
        entry=100.0,
        stop=98.0,
        target=106.0,
        reward_risk=3.0,
    )


def hold_decision() -> StrategyDecision:
    return StrategyDecision(
        strategy="pullback-v1",
        candidate_action="HOLD",
        base_confidence=HOLD_BASE_CONFIDENCE,
        reason="no setup: reward_risk",
        filters={},
        setup={},
    )


def test_confirm_within_band_untouched():
    action, conf, review = enforce_llm_review(buy_decision(), "BUY", 75)
    assert (action, conf) == ("BUY", 75)
    assert review["coercions"] == []
    assert review["veto"] is False


def test_shade_clamped_high():
    action, conf, review = enforce_llm_review(buy_decision(70), "BUY", 95)
    assert (action, conf) == ("BUY", 70 + LLM_SHADE_BAND)
    assert "confidence_clamped" in review["coercions"]


def test_shade_clamped_low():
    action, conf, review = enforce_llm_review(buy_decision(70), "BUY", 10)
    assert (action, conf) == ("BUY", 70 - LLM_SHADE_BAND)
    assert "confidence_clamped" in review["coercions"]


def test_sell_is_illegal():
    action, conf, review = enforce_llm_review(buy_decision(70), "SELL", 80)
    assert action == "BUY"  # coerced back to the candidate
    assert "illegal_action" in review["coercions"]
    assert review["raw_llm_action"] == "SELL"


def test_buy_on_hold_candidate_is_illegal():
    action, conf, review = enforce_llm_review(hold_decision(), "BUY", 85)
    assert action == "HOLD"
    assert "illegal_action" in review["coercions"]
    # confidence still clamps around the HOLD base
    assert conf == HOLD_BASE_CONFIDENCE + LLM_SHADE_BAND


def test_legitimate_veto_passes_through():
    reasoning = "VETO: CFO resigned this morning; chart can't see it.\nMore detail."
    action, conf, review = enforce_llm_review(buy_decision(70), "HOLD", 35, reasoning)
    assert (action, conf) == ("HOLD", 35)  # veto keeps the LLM's confidence
    assert review["veto"] is True
    assert review["veto_reason"] == "CFO resigned this morning; chart can't see it."
    assert review["coercions"] == []


def test_veto_without_tagged_reason():
    action, conf, review = enforce_llm_review(buy_decision(), "HOLD", 40, "Just nervous.")
    assert review["veto"] is True
    assert review["veto_reason"] is None
