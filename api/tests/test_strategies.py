"""Strategy framework: regime filters, the three entry rules, LLM-review
enforcement. Synthetic facts bundles, same pattern as test_gate.py."""

from bull_api.strategy import (
    REGISTRY,
    bounce,
    breakout,
    enforce_llm_review,
    pullback,
    wyckoff,
)
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
    assert list(REGISTRY) == [
        "pullback-v1",
        "breakout-v1",
        "bounce-v1",
        "wyckoff-spring-v1",
    ]


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


# --- breakout-v1 -----------------------------------------------------------------


def breakout_bundle() -> dict:
    closes = [90.0 + i * 0.3 for i in range(30)]  # rises to 98.7
    facts = bundle(
        prices=[{"date": f"2026-05-{i:02d}", "close": c} for i, c in enumerate(closes, 1)]
        + [{"date": "2026-06-08", "close": 100.0}],
    )
    facts["indicators"]["volume_current"] = 2_000_000  # 2.0x
    facts["support_resistance"]["support"][0]["price"] = 95.0  # risk 5% <= 8%
    facts["support_resistance"]["resistance"] = []  # ATH → measured move
    return facts


def test_breakout_full_pass_measured_move():
    d = breakout.evaluate(breakout_bundle())
    assert d.candidate_action == "BUY"
    # 60 + volume>=2x + MACD>0 + VIX calm = 75
    assert d.base_confidence == 75
    assert (d.entry, d.stop) == (100.0, 95.0)
    assert d.target == 110.0  # entry + 2 × risk
    assert d.reward_risk == 2.0


def test_breakout_uses_overhead_resistance_when_present():
    facts = breakout_bundle()
    facts["support_resistance"]["resistance"] = [{"price": 112.0, "touch_count": 1}]
    d = breakout.evaluate(facts)
    assert d.candidate_action == "BUY"
    assert d.target == 112.0


def test_breakout_not_a_new_high():
    facts = breakout_bundle()
    facts["prices"][-1]["close"] = 98.0  # below the prior high
    facts["indicators"]["sma_50"] = 94.0  # keep extension sane
    hold_with(breakout.evaluate(facts), "closing_high_breakout")


def test_breakout_volume_too_light():
    facts = breakout_bundle()
    facts["indicators"]["volume_current"] = 1_200_000  # 1.2x < 1.5x
    hold_with(breakout.evaluate(facts), "volume_confirms")


def test_breakout_risk_too_wide():
    facts = breakout_bundle()
    facts["support_resistance"]["support"][0]["price"] = 91.0  # 9% risk
    hold_with(breakout.evaluate(facts), "risk_bounded")


def test_breakout_insufficient_history():
    facts = breakout_bundle()
    facts["prices"] = facts["prices"][-10:]  # < MIN_PRIOR_BARS prior closes
    hold_with(breakout.evaluate(facts), "closing_high_breakout")


# --- bounce-v1 --------------------------------------------------------------------


def bounce_bundle() -> dict:
    facts = bundle()
    facts["indicators"]["rsi_14"] = 32.0
    facts["support_resistance"]["resistance"] = [
        {"price": 103.0, "touch_count": 2},  # nearest — the reversion target
        {"price": 110.0, "touch_count": 1},
    ]
    return facts


def test_bounce_full_pass_targets_nearest_resistance():
    d = bounce.evaluate(bounce_bundle())
    assert d.candidate_action == "BUY"
    # 60 + 3 touches + VIX calm = 70 (RSI 32 > 30, no oversold bonus)
    assert d.base_confidence == 70
    assert d.target == 103.0
    assert d.reward_risk == 1.5  # (103-100)/(100-98)
    assert d.stop == 98.0


def test_bounce_deep_oversold_bonus():
    facts = bounce_bundle()
    facts["indicators"]["rsi_14"] = 28.0
    assert bounce.evaluate(facts).base_confidence == 75


def test_bounce_not_oversold():
    facts = bounce_bundle()
    facts["indicators"]["rsi_14"] = 41.0
    hold_with(bounce.evaluate(facts), "oversold")


def test_bounce_reward_too_thin():
    facts = bounce_bundle()
    facts["support_resistance"]["resistance"][0]["price"] = 101.0  # 0.5:1
    hold_with(bounce.evaluate(facts), "reward_risk")


# --- wyckoff-spring-v1 -------------------------------------------------------------


def wyckoff_bundle() -> dict:
    """A 25-bar trading range (support 100, top 108) + a 5-bar spring window:
    undercut to 99.7 on quiet volume, last close 100.8 back inside the range."""
    range_bar = {"open": 103.0, "high": 108.0, "low": 100.0, "close": 104.0, "volume": 1_000_000}
    spring_window = [
        {"open": 102.0, "high": 103.0, "low": 100.5, "close": 102.0, "volume": 1_000_000},
        {"open": 102.0, "high": 102.5, "low": 100.6, "close": 101.5, "volume": 1_000_000},
        {"open": 101.0, "high": 101.5, "low": 99.7, "close": 100.2, "volume": 700_000},  # spring
        {"open": 100.3, "high": 100.9, "low": 100.1, "close": 100.5, "volume": 900_000},
        {"open": 100.5, "high": 101.0, "low": 100.2, "close": 100.8, "volume": 1_000_000},
    ]
    facts = bundle(
        prices=[{**range_bar, "date": f"2026-04-{i:02d}"} for i in range(1, 26)]
        + [{**b, "date": f"2026-05-{i:02d}"} for i, b in enumerate(spring_window, 1)],
    )
    facts["indicators"]["sma_50"] = 98.0  # last 100.8 → +2.9%, stack still up
    facts["indicators"]["sma_200"] = 90.0
    return facts


def test_wyckoff_full_pass():
    d = wyckoff.evaluate(wyckoff_bundle())
    assert d.candidate_action == "BUY"
    # 60 + no-supply (0.7x) + VIX calm; no RS bonus (spy pct unavailable) = 70
    assert d.base_confidence == 70
    assert d.entry == 100.8
    assert d.stop == round(99.7 * 0.995, 4)
    assert d.target == 108.0
    assert d.reward_risk is not None and d.reward_risk >= 3.0


def test_wyckoff_rs_bonus_when_outperforming_spy():
    facts = wyckoff_bundle()
    facts["market_context"]["spy"]["pct_change_20d"] = -5.0  # ticker did ~-3%
    assert wyckoff.evaluate(facts).base_confidence == 75


def test_wyckoff_no_undercut():
    facts = wyckoff_bundle()
    for b in facts["prices"][-5:]:
        b["low"] = max(b["low"], 100.2)  # never pierces support
    hold_with(wyckoff.evaluate(facts), "spring_undercut")


def test_wyckoff_undercut_too_deep_is_breakdown():
    facts = wyckoff_bundle()
    facts["prices"][-3]["low"] = 95.0  # 5% under support
    hold_with(wyckoff.evaluate(facts), "spring_undercut")


def test_wyckoff_no_recovery():
    facts = wyckoff_bundle()
    facts["prices"][-1]["close"] = 99.5  # still below support
    hold_with(wyckoff.evaluate(facts), "recovered_into_range")


def test_wyckoff_climactic_volume_fails_no_supply():
    facts = wyckoff_bundle()
    facts["prices"][-3]["volume"] = 2_000_000  # 2.0x average
    hold_with(wyckoff.evaluate(facts), "no_supply_volume")


def test_wyckoff_range_too_tall():
    facts = wyckoff_bundle()
    facts["prices"][0]["high"] = 125.0
    hold_with(wyckoff.evaluate(facts), "base_forming")


def test_wyckoff_reward_too_thin_near_range_top():
    facts = wyckoff_bundle()
    facts["prices"][-1]["close"] = 105.0  # recovered but most of the move is gone
    hold_with(wyckoff.evaluate(facts), "reward_risk")


def test_wyckoff_insufficient_bars():
    facts = wyckoff_bundle()
    facts["prices"] = facts["prices"][-10:]
    hold_with(wyckoff.evaluate(facts), "base_forming")


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
