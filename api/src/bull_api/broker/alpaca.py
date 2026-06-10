"""Alpaca paper-trading wrapper.

CRITICAL: `paper=True` is hardcoded. Never construct a live TradingClient.
"""

from functools import lru_cache
from typing import Any, TypedDict

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    GetPortfolioHistoryRequest,
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

from ..config import settings


class AlpacaAccount(TypedDict):
    equity: float
    cash: float
    buying_power: float


class AlpacaPosition(TypedDict):
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float


class AlpacaPortfolioHistory(TypedDict):
    timestamp: list[int]
    equity: list[float]
    profit_loss: list[float]
    profit_loss_pct: list[float | None]
    base_value: float | None
    timeframe: str


@lru_cache(maxsize=1)
def _client() -> TradingClient:
    if not settings.alpaca_api_key or not settings.alpaca_api_secret:
        raise RuntimeError(
            "Alpaca credentials missing. Set ALPACA_API_KEY and ALPACA_API_SECRET in api/.env."
        )
    # paper=True is intentional and hardcoded. Bull is a paper-trading-only app.
    return TradingClient(
        settings.alpaca_api_key,
        settings.alpaca_api_secret,
        paper=True,
    )


def _f(x: Any) -> float:
    if x is None:
        return 0.0
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _enum_value(x: Any) -> str:
    return str(x.value if hasattr(x, "value") else x)


def get_account() -> AlpacaAccount:
    acct = _client().get_account()
    return {
        "equity": _f(acct.equity),
        "cash": _f(acct.cash),
        "buying_power": _f(acct.buying_power),
    }


def get_positions() -> list[AlpacaPosition]:
    return [
        {
            "symbol": p.symbol,
            "qty": _f(p.qty),
            "avg_entry_price": _f(p.avg_entry_price),
            "market_value": _f(p.market_value),
            "unrealized_pl": _f(p.unrealized_pl),
        }
        for p in _client().get_all_positions()
    ]


def place_order(
    symbol: str,
    side: str,
    notional: float | None = None,
    qty: float | None = None,
) -> dict[str, Any]:
    """Market order, DAY TIF. Provide exactly one of `notional` (dollars) or
    `qty` (shares). Always paper."""
    if (notional is None) == (qty is None):
        raise ValueError("Provide exactly one of notional or qty")
    side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    request = MarketOrderRequest(
        symbol=symbol.upper(),
        notional=notional,
        qty=qty,
        side=side_enum,
        time_in_force=TimeInForce.DAY,
    )
    order = _client().submit_order(request)
    return {
        "alpaca_order_id": str(order.id),
        "symbol": order.symbol,
        "side": side_enum.value,
        "qty": _f(order.qty),
        "notional": _f(order.notional),
        "status": _enum_value(order.status),
        "submitted_at": order.submitted_at,
        "filled_avg_price": _f(order.filled_avg_price),
    }


def place_bracket_order(
    symbol: str,
    qty: int,
    stop_price: float,
    target_price: float,
) -> dict[str, Any]:
    """Market BUY with attached GTC stop-loss + take-profit legs — Alpaca
    executes the exits server-side, no polling needed on our end.

    Bracket constraints: whole-share qty (no notional, no fractionals) and the
    legs must straddle the market (stop below, target above). Always paper.
    """
    if qty < 1:
        raise ValueError("Bracket orders need a whole-share qty >= 1")
    if stop_price >= target_price:
        raise ValueError("stop_price must be below target_price")
    request = MarketOrderRequest(
        symbol=symbol.upper(),
        qty=int(qty),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.GTC,  # legs must outlive the entry day
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=round(target_price, 2)),
        stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
    )
    order = _client().submit_order(request)
    legs: dict[str, str] = {}
    for leg in order.legs or []:
        leg_type = _enum_value(getattr(leg, "order_type", None) or getattr(leg, "type", ""))
        if leg_type == "limit":
            legs["take_profit"] = str(leg.id)
        elif leg_type == "stop":
            legs["stop_loss"] = str(leg.id)
    return {
        "alpaca_order_id": str(order.id),
        "symbol": order.symbol,
        "side": OrderSide.BUY.value,
        "qty": _f(order.qty),
        "notional": None,
        "status": _enum_value(order.status),
        "submitted_at": order.submitted_at,
        "filled_avg_price": _f(order.filled_avg_price),
        "legs": legs,
    }


def cancel_open_orders(symbol: str) -> int:
    """Cancel every open order for `symbol` (e.g. live bracket legs before a
    close — Alpaca rejects closing shares that are held by open orders).
    Returns the number of cancellations requested."""
    request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol.upper()])
    open_orders = _client().get_orders(filter=request)
    for o in open_orders:
        _client().cancel_order_by_id(o.id)
    return len(open_orders)


def close_position(symbol: str) -> dict[str, Any]:
    order = _client().close_position(symbol.upper())
    return {
        "alpaca_order_id": str(order.id),
        "symbol": symbol.upper(),
        "side": _enum_value(order.side),
        "status": _enum_value(order.status),
        "submitted_at": order.submitted_at,
    }


def get_portfolio_history(period: str = "1M", timeframe: str | None = None) -> AlpacaPortfolioHistory:
    """Account equity time-series. `period` like 1D/1W/1M/3M/1Y; `timeframe` like 5Min/15Min/1H/1D.
    If `timeframe` is None, Alpaca picks a sensible default for the period."""
    req = GetPortfolioHistoryRequest(period=period, timeframe=timeframe)
    h = _client().get_portfolio_history(history_filter=req)
    return {
        "timestamp": list(h.timestamp or []),
        "equity": [_f(v) for v in (h.equity or [])],
        "profit_loss": [_f(v) for v in (h.profit_loss or [])],
        "profit_loss_pct": [None if v is None else _f(v) for v in (h.profit_loss_pct or [])],
        "base_value": None if h.base_value is None else _f(h.base_value),
        "timeframe": h.timeframe,
    }


def get_recent_orders(limit: int = 50) -> list[dict[str, Any]]:
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
    orders = _client().get_orders(filter=request)
    return [
        {
            "alpaca_order_id": str(o.id),
            "symbol": o.symbol,
            "side": _enum_value(o.side),
            "qty": _f(o.qty),
            "notional": _f(o.notional),
            "status": _enum_value(o.status),
            "submitted_at": o.submitted_at,
            "filled_avg_price": _f(o.filled_avg_price),
        }
        for o in orders
    ]


if __name__ == "__main__":
    acct = get_account()
    print(f"Paper account — equity ${acct['equity']:,.2f}  cash ${acct['cash']:,.2f}  "
          f"buying power ${acct['buying_power']:,.2f}")
    positions = get_positions()
    print(f"{len(positions)} open position(s)")
    for p in positions:
        print(f"  {p['symbol']:6s}  qty={p['qty']:.4f}  "
              f"@ ${p['avg_entry_price']:.2f}  pl ${p['unrealized_pl']:+.2f}")
