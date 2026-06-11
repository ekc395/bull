"""Backtest simulation core: fill rules, exit ordering, lookahead discipline.

Synthetic OHLCV frames with known geometry; no network, no strategies — the
`decide` callback is injected so each test controls exactly when a signal
fires and with what bracket.
"""

from datetime import date

import pandas as pd

from bull_api.backtest import (
    SimResult,
    Trade,
    _days_until_earnings,
    _sharpe,
    build_facts_asof,
    portfolio_pnl,
    simulate,
    strategy_summary,
)
from bull_api.strategy.base import StrategyDecision

FLAT = (100.0, 101.0, 99.0, 100.0)  # o, h, l, c — touches nothing interesting


def make_df(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-02", periods=len(bars))
    return pd.DataFrame(
        {
            "Open": [b[0] for b in bars],
            "High": [b[1] for b in bars],
            "Low": [b[2] for b in bars],
            "Close": [b[3] for b in bars],
            "Volume": [1_000_000] * len(bars),
        },
        index=idx,
    )


def buy(stop: float = 95.0, target: float = 103.0, max_hold: int = 20) -> StrategyDecision:
    return StrategyDecision(
        strategy="test-v1",
        candidate_action="BUY",
        base_confidence=65,
        reason="test",
        filters={},
        setup={},
        entry=100.0,
        stop=stop,
        target=target,
        reward_risk=1.6,
        max_hold_trading_days=max_hold,
    )


def signal_at(idx: int, decision: StrategyDecision):
    return lambda i: decision if i == idx else None


# --- fills -------------------------------------------------------------------------


def test_entry_fills_at_next_open():
    df = make_df([FLAT, FLAT, (100.5, 101.5, 99.5, 100.5)] + [FLAT] * 25)
    sim = simulate(df, signal_at(1, buy()))
    assert len(sim.trades) == 1
    assert sim.trades[0].entry_price == 100.5  # bar 2's open, not bar 1's close
    assert sim.trades[0].entry_date == df.index[2].date().isoformat()


def test_target_exit_at_target_price():
    df = make_df([FLAT, FLAT, FLAT, (100.0, 104.0, 99.0, 102.0)] + [FLAT] * 5)
    sim = simulate(df, signal_at(1, buy(target=103.0)))
    (t,) = sim.trades
    assert t.exit_reason == "target"
    assert t.exit_price == 103.0  # the limit price, not the bar high/close
    assert t.return_pct > 0


def test_stop_exit_at_stop_price():
    df = make_df([FLAT, FLAT, FLAT, (100.0, 101.0, 94.0, 96.0)] + [FLAT] * 5)
    sim = simulate(df, signal_at(1, buy(stop=95.0)))
    (t,) = sim.trades
    assert t.exit_reason == "stop"
    assert t.exit_price == 95.0


def test_ambiguous_bar_counts_as_stop():
    # One bar touches BOTH the stop and the target → conservative: stop first.
    df = make_df([FLAT, FLAT, FLAT, (100.0, 106.0, 94.0, 100.0)] + [FLAT] * 5)
    sim = simulate(df, signal_at(1, buy(stop=95.0, target=103.0)))
    (t,) = sim.trades
    assert t.exit_reason == "stop"
    assert t.exit_price == 95.0


def test_gap_through_stop_fills_at_open():
    df = make_df([FLAT, FLAT, FLAT, (93.0, 96.0, 92.0, 95.5)] + [FLAT] * 5)
    sim = simulate(df, signal_at(1, buy(stop=95.0)))
    (t,) = sim.trades
    assert t.exit_reason == "stop"
    assert t.exit_price == 93.0  # worse than the stop — gap slippage is real


def test_gap_through_target_fills_at_open():
    df = make_df([FLAT, FLAT, FLAT, (105.0, 106.0, 104.0, 105.5)] + [FLAT] * 5)
    sim = simulate(df, signal_at(1, buy(target=103.0)))
    (t,) = sim.trades
    assert t.exit_reason == "target"
    assert t.exit_price == 105.0  # better than the limit — favorable gap


def test_stop_can_hit_on_entry_bar_after_open():
    # Entry bar opens fine then breaks down intraday — the bracket stop fills.
    df = make_df([FLAT, FLAT, (100.0, 100.5, 94.0, 94.5)] + [FLAT] * 5)
    sim = simulate(df, signal_at(1, buy(stop=95.0)))
    (t,) = sim.trades
    assert t.exit_reason == "stop"
    assert t.hold_bars == 0


def test_time_stop_exits_at_close():
    df = make_df([FLAT] * 30)
    sim = simulate(df, signal_at(1, buy(stop=90.0, target=120.0, max_hold=3)))
    (t,) = sim.trades
    assert t.exit_reason == "time_stop"
    assert t.hold_bars == 3
    assert t.exit_price == 100.0  # the close of entry_idx + max_hold
    assert t.exit_date == df.index[2 + 3].date().isoformat()


def test_open_position_closes_at_end_of_data():
    df = make_df([FLAT] * 6)
    sim = simulate(df, signal_at(1, buy(stop=90.0, target=120.0, max_hold=50)))
    (t,) = sim.trades
    assert t.exit_reason == "end_of_data"
    assert t.exit_date == df.index[-1].date().isoformat()


# --- discipline ----------------------------------------------------------------------


def test_no_lookahead_signal_on_last_bar_cannot_enter():
    df = make_df([FLAT] * 5)
    sim = simulate(df, signal_at(4, buy()))  # last bar: no t+1 open to fill at
    assert sim.signals == 0
    assert sim.trades == []


def test_entry_skipped_when_next_open_gaps_through_stop():
    df = make_df([FLAT, FLAT, (94.0, 96.0, 92.0, 95.0)] + [FLAT] * 5)
    sim = simulate(df, signal_at(1, buy(stop=95.0)))
    assert sim.signals == 1
    assert sim.trades == []  # bracket would fill instantly; trade skipped


def test_one_position_at_a_time():
    # Signal every day; trades must be sequential, never overlapping.
    df = make_df([FLAT] * 20)
    sim = simulate(df, lambda i: buy(stop=90.0, target=120.0, max_hold=3))
    assert len(sim.trades) >= 2
    for prev, nxt in zip(sim.trades, sim.trades[1:]):
        assert nxt.entry_date > prev.exit_date or (
            nxt.entry_date == prev.exit_date and prev.exit_reason == "time_stop"
        )
    # while in a position, decide() is not called
    assert sim.days_evaluated < len(df) - 1


def test_start_idx_respected():
    df = make_df([FLAT] * 10)
    sim = simulate(df, lambda i: None, start_idx=6)
    assert sim.days_evaluated == 3  # bars 6, 7, 8 (last bar never evaluated)


# --- point-in-time facts ---------------------------------------------------------------


def test_build_facts_asof_sees_nothing_past_bar_i():
    bars = [FLAT] * 25
    bars.append((500.0, 500.0, 500.0, 500.0))  # absurd future bar
    df = make_df(bars)
    i = 24
    facts = build_facts_asof(
        "TEST",
        df,
        i,
        spy_above_sma_50=True,
        sector_etf="XLK",
        sector_above_sma_50=True,
        vix_level=14.0,
        days_until_earnings=None,
    )
    assert facts["as_of"] == df.index[i].date().isoformat()
    assert facts["prices"][-1]["date"] == df.index[i].date().isoformat()
    assert all(p["close"] < 500 for p in facts["prices"])
    # indicators computed on the window ending at i — the 500 bar can't leak in
    assert facts["indicators"]["sma_20"] == 100.0
    assert facts["market_context"]["vix_state"] == "calm"


# --- helpers -----------------------------------------------------------------------------


def test_days_until_earnings_upcoming():
    dates = [date(2024, 2, 1), date(2024, 5, 1)]
    assert _days_until_earnings(date(2024, 4, 25), dates) == 6


def test_days_until_earnings_just_reported():
    dates = [date(2024, 2, 1), date(2024, 5, 1)]
    assert _days_until_earnings(date(2024, 5, 3), dates) == -2


def test_days_until_earnings_unknown():
    assert _days_until_earnings(date(2024, 4, 25), []) is None


def pnl_trade(
    entry_date: str,
    entry_price: float,
    exit_date: str,
    exit_price: float,
    ticker: str = "T",
) -> Trade:
    return Trade(
        ticker=ticker,
        strategy="s",
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=exit_date,
        exit_price=exit_price,
        exit_reason="target",
        return_pct=(exit_price / entry_price - 1.0) * 100.0,
        hold_bars=3,
        confidence=65,
    )


def closes(values: list[float], start: str = "2024-01-02") -> pd.Series:
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx)


def test_portfolio_pnl_single_winner():
    # 10% of $100k = $10k at $100 → 100 shares; exit $110 → +$1,000.
    trades = [pnl_trade("2024-01-03", 100.0, "2024-01-08", 110.0)]
    p = portfolio_pnl(
        trades, {"T": closes([100.0] * 4 + [110.0] * 4)}, start_cash=100_000, alloc_pct=10.0
    )
    assert p["trades_taken"] == 1
    assert p["end_equity"] == 101_000.0
    assert p["net_pnl_usd"] == 1_000.0
    assert p["return_pct"] == 1.0


def test_portfolio_pnl_skips_entry_when_cash_short():
    # alloc 60%: first entry takes $60k, second needs $60k but only $40k remains.
    trades = [
        pnl_trade("2024-01-03", 100.0, "2024-01-09", 100.0, ticker="A"),
        pnl_trade("2024-01-03", 50.0, "2024-01-09", 50.0, ticker="B"),
    ]
    series = {"A": closes([100.0] * 6), "B": closes([50.0] * 6)}
    p = portfolio_pnl(trades, series, start_cash=100_000, alloc_pct=60.0)
    assert p["trades_taken"] == 1
    assert p["trades_skipped_no_cash"] == 1
    assert p["end_equity"] == 100_000.0  # flat trade, nothing gained or lost


def test_portfolio_pnl_marks_drawdown_to_market_daily():
    # Position dips to 80 mid-hold before exiting at 110: equity trough is
    # $90k cash + 100 sh × $80 = $98k → -2% drawdown even though the TRADE won.
    trades = [pnl_trade("2024-01-03", 100.0, "2024-01-10", 110.0)]
    series = {"T": closes([100.0, 100.0, 100.0, 80.0, 90.0, 105.0, 110.0])}
    p = portfolio_pnl(trades, series, start_cash=100_000, alloc_pct=10.0)
    assert p["max_drawdown_pct"] == -2.0
    assert p["net_pnl_usd"] == 1_000.0


def test_portfolio_pnl_empty():
    p = portfolio_pnl([], {}, start_cash=100_000, alloc_pct=10.0)
    assert p["end_equity"] == 100_000
    assert p["trades_taken"] == 0
    assert p["max_drawdown_pct"] is None
    assert p["sharpe"] is None


def test_sharpe_none_on_flat_curve():
    # zero variance (all-cash account) → undefined, not divide-by-zero
    assert _sharpe([100_000.0] * 10) is None


def test_sharpe_positive_when_equity_rises():
    # +1% / flat alternation: positive mean daily return, nonzero variance
    curve = [100_000.0]
    for i in range(10):
        curve.append(curve[-1] * (1.01 if i % 2 == 0 else 1.0))
    assert _sharpe(curve) > 0


def test_portfolio_pnl_records_sharpe():
    trades = [pnl_trade("2024-01-03", 100.0, "2024-01-08", 110.0)]
    p = portfolio_pnl(
        trades, {"T": closes([100.0] * 4 + [110.0] * 4)}, start_cash=100_000, alloc_pct=10.0
    )
    assert p["sharpe"] is not None
    assert p["sharpe"] > 0


def test_strategy_summary_numbers():
    def trade(ret: float, reason: str, exit_date: str) -> Trade:
        return Trade(
            ticker="T",
            strategy="s",
            entry_date="2024-01-02",
            entry_price=100.0,
            exit_date=exit_date,
            exit_price=100.0 + ret,
            exit_reason=reason,
            return_pct=ret,
            hold_bars=5,
            confidence=65,
        )

    results = {
        "T": SimResult(
            trades=[trade(10.0, "target", "2024-02-01"), trade(-5.0, "stop", "2024-03-01")],
            days_evaluated=100,
            signals=2,
        )
    }
    s = strategy_summary(results)
    assert s["trades"] == 2
    assert s["win_rate"] == 0.5
    assert s["fire_rate_pct"] == 2.0
    assert s["total_return_pct"] == 4.5  # 1.10 × 0.95 − 1
    assert s["exit_reasons"] == {"target": 1, "stop": 1}
    assert s["per_ticker"]["T"]["trades"] == 2
