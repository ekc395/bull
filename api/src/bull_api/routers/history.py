"""GET /orders, /trades — paper-order history and paired round-trip trades."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Order
from ..repos import orders as orepo
from ..schemas import OrderResponse, TradeResponse

router = APIRouter()

# Order statuses that never held a position — excluded from trade pairing.
_UNFILLED = {"canceled", "expired", "rejected"}


def _make_trade(buy: Order | None, sell: Order | None) -> TradeResponse:
    first = sell or buy
    assert first is not None
    buy_price = buy.filled_avg_price if buy else None
    sell_price = sell.filled_avg_price if sell else None
    # Whole-lot closes only today (autotrade skips held tickers, closes are
    # full-position), so the sell qty is the trade qty; notional buys with no
    # qty anywhere derive it from the entry fill.
    qty = (sell.qty if sell else None) or (buy.qty if buy else None)
    if qty is None and buy is not None and buy.notional and buy_price:
        qty = buy.notional / buy_price
    pnl = (sell_price - buy_price) * qty if buy_price and sell_price and qty else None
    return_pct = (sell_price / buy_price - 1) * 100 if buy_price and sell_price else None
    notional = buy.notional if buy else None
    if notional is None and qty and buy_price:
        notional = qty * buy_price
    return TradeResponse(
        ticker=first.ticker,
        status="closed" if sell else "open",
        qty=qty,
        buy_order_id=buy.id if buy else None,
        sell_order_id=sell.id if sell else None,
        buy_submitted_at=buy.submitted_at if buy else None,
        sell_submitted_at=sell.submitted_at if sell else None,
        buy_price=buy_price,
        sell_price=sell_price,
        notional=notional,
        exit_reason=sell.exit_reason if sell else None,
        pnl=pnl,
        return_pct=return_pct,
    )


def _pair_trades(orders: list[Order]) -> list[TradeResponse]:
    """Pair entry buys with exit sells into round-trip trades.

    Walks fills oldest-first keeping per-ticker open lots. A sell matches the
    open lot sharing its verdict_id (bracket legs and time stops inherit it),
    else the earliest lot for the ticker (FIFO — manual closes carry none),
    else it becomes a sell-only row. Leftover lots are open trades.
    """
    rows = sorted(
        (o for o in orders if o.status not in _UNFILLED),
        key=lambda o: o.submitted_at,
    )
    open_lots: dict[str, list[Order]] = {}
    trades: list[TradeResponse] = []
    for o in rows:
        if o.side == "buy":
            open_lots.setdefault(o.ticker, []).append(o)
            continue
        lots = open_lots.get(o.ticker, [])
        buy = None
        if o.verdict_id is not None:
            buy = next((b for b in lots if b.verdict_id == o.verdict_id), None)
        if buy is None and lots:
            buy = lots[0]
        if buy is not None:
            lots.remove(buy)
        trades.append(_make_trade(buy, o))
    for lots in open_lots.values():
        trades.extend(_make_trade(b, None) for b in lots)
    trades.sort(
        key=lambda t: t.sell_submitted_at or t.buy_submitted_at,  # type: ignore[arg-type,return-value]
        reverse=True,
    )
    return trades


def _order_to_response(o: Order) -> OrderResponse:
    return OrderResponse(
        id=o.id,
        alpaca_order_id=o.alpaca_order_id,
        ticker=o.ticker,
        side=o.side,  # type: ignore[arg-type]
        qty=o.qty,
        notional=o.notional,
        status=o.status,
        submitted_at=o.submitted_at,
        filled_avg_price=o.filled_avg_price,
        order_class=o.order_class,
        stop_price=o.stop_price,
        target_price=o.target_price,
        exit_reason=o.exit_reason,
    )


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[OrderResponse]:
    rows = await orepo.list_recent(limit, session)
    return [_order_to_response(o) for o in rows]


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[TradeResponse]:
    # Fetch a deep window so old entries still pair with recent exits.
    rows = await orepo.list_recent(1000, session)
    return _pair_trades(rows)[:limit]
