"""`routers.history._pair_trades` — pairing order legs into round-trip trades.

Pure function over Order rows: verdict_id match first, per-ticker FIFO for
manual closes, open lots for unmatched buys, sell-only orphans, and P&L only
when both fills and a qty are known.
"""

from datetime import datetime, timedelta, timezone

from bull_api.models import Order
from bull_api.routers.history import _pair_trades

_T0 = datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc)
_ids = iter(range(1, 1000))


def _order(
    ticker="AAPL",
    side="buy",
    *,
    qty=None,
    notional=None,
    status="filled",
    minutes=0,
    filled_avg_price=None,
    verdict_id=None,
    exit_reason=None,
) -> Order:
    i = next(_ids)
    return Order(
        id=i,
        verdict_id=verdict_id,
        alpaca_order_id=f"alp-{i}",
        ticker=ticker,
        side=side,
        qty=qty,
        notional=notional,
        status=status,
        submitted_at=_T0 + timedelta(minutes=minutes),
        filled_avg_price=filled_avg_price,
        exit_reason=exit_reason,
    )


def test_pairs_by_verdict_id_over_fifo():
    b1 = _order(qty=10, filled_avg_price=100.0, verdict_id=1, minutes=0)
    b2 = _order(qty=5, filled_avg_price=110.0, verdict_id=2, minutes=1)
    s2 = _order(side="sell", qty=5, filled_avg_price=121.0, verdict_id=2, minutes=2)
    trades = _pair_trades([b1, b2, s2])
    closed = [t for t in trades if t.status == "closed"]
    assert len(closed) == 1
    t = closed[0]
    assert t.buy_order_id == b2.id
    assert t.buy_price == 110.0
    assert t.sell_price == 121.0
    assert t.pnl == 5 * 11.0
    assert round(t.return_pct, 2) == 10.0


def test_fifo_fallback_for_manual_close_without_verdict_id():
    b1 = _order(qty=10, filled_avg_price=100.0, verdict_id=1, minutes=0)
    b2 = _order(qty=10, filled_avg_price=105.0, verdict_id=2, minutes=1)
    s = _order(side="sell", qty=10, filled_avg_price=110.0, minutes=2, exit_reason="manual")
    trades = _pair_trades([b1, b2, s])
    closed = [t for t in trades if t.status == "closed"]
    assert len(closed) == 1
    assert closed[0].buy_order_id == b1.id  # earliest lot, not b2
    assert closed[0].exit_reason == "manual"
    open_ids = [t.buy_order_id for t in trades if t.status == "open"]
    assert open_ids == [b2.id]


def test_unmatched_buy_is_open_trade():
    b = _order(qty=3, filled_avg_price=50.0, verdict_id=7)
    (t,) = _pair_trades([b])
    assert t.status == "open"
    assert t.buy_price == 50.0
    assert t.sell_order_id is None
    assert t.pnl is None


def test_sell_without_any_lot_is_orphan():
    s = _order(side="sell", qty=4, filled_avg_price=20.0)
    (t,) = _pair_trades([s])
    assert t.status == "closed"
    assert t.buy_order_id is None
    assert t.sell_price == 20.0
    assert t.pnl is None


def test_qty_derived_from_notional_when_missing():
    b = _order(notional=1000.0, filled_avg_price=100.0, verdict_id=1, minutes=0)
    s = _order(side="sell", filled_avg_price=105.0, verdict_id=1, minutes=1)
    (t,) = _pair_trades([b, s])
    assert t.qty == 10.0
    assert t.pnl == 50.0


def test_missing_fill_price_means_no_pnl():
    b = _order(qty=10, verdict_id=1, minutes=0)  # never backfilled
    s = _order(side="sell", qty=10, filled_avg_price=99.0, verdict_id=1, minutes=1)
    (t,) = _pair_trades([b, s])
    assert t.status == "closed"
    assert t.buy_price is None
    assert t.pnl is None
    assert t.return_pct is None


def test_canceled_orders_excluded_from_pairing():
    b_cancel = _order(qty=10, filled_avg_price=100.0, status="canceled", verdict_id=1, minutes=0)
    b = _order(qty=10, filled_avg_price=102.0, verdict_id=2, minutes=1)
    s = _order(side="sell", qty=10, filled_avg_price=103.0, minutes=2)
    trades = _pair_trades([b_cancel, b, s])
    assert len(trades) == 1
    assert trades[0].buy_order_id == b.id


def test_tickers_do_not_cross_pair():
    b_a = _order(ticker="AAPL", qty=1, filled_avg_price=100.0, minutes=0)
    b_m = _order(ticker="MSFT", qty=1, filled_avg_price=400.0, minutes=1)
    s_m = _order(ticker="MSFT", side="sell", qty=1, filled_avg_price=410.0, minutes=2)
    trades = _pair_trades([b_a, b_m, s_m])
    closed = [t for t in trades if t.status == "closed"]
    assert [t.ticker for t in closed] == ["MSFT"]
    assert [t.ticker for t in trades if t.status == "open"] == ["AAPL"]


def test_sorted_desc_by_close_then_open_time():
    b_old = _order(ticker="AAPL", qty=1, filled_avg_price=1.0, verdict_id=1, minutes=0)
    s_old = _order(ticker="AAPL", side="sell", qty=1, filled_avg_price=2.0, verdict_id=1, minutes=5)
    b_open = _order(ticker="MSFT", qty=1, filled_avg_price=1.0, verdict_id=2, minutes=10)
    trades = _pair_trades([b_old, s_old, b_open])
    assert [t.ticker for t in trades] == ["MSFT", "AAPL"]
