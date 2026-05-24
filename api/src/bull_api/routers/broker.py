"""Alpaca paper-trading endpoints: account, positions, orders."""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..broker import alpaca
from ..config import settings
from ..db import get_session
from ..models import Order
from ..repos import orders as orepo
from ..repos import verdicts as vrepo
from ..schemas import (
    AccountResponse,
    ExecuteOrderRequest,
    OrderResponse,
    PortfolioHistoryResponse,
    PositionResponse,
)
from ..time import now_utc

router = APIRouter()


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
    )


@router.get("/account", response_model=AccountResponse)
async def get_account() -> AccountResponse:
    try:
        data = await asyncio.to_thread(alpaca.get_account)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return AccountResponse(**data)


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions() -> list[PositionResponse]:
    try:
        data = await asyncio.to_thread(alpaca.get_positions)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return [PositionResponse(**p) for p in data]


# Allowed values mirror Alpaca's portfolio-history API. The frontend's range
# toggle is the only intended caller, but we validate explicitly so a typo'd
# URL doesn't get forwarded to Alpaca and surface as an opaque 422.
_ALLOWED_PERIODS = {"1D", "1W", "1M", "3M", "1Y"}
_ALLOWED_TIMEFRAMES = {"1Min", "5Min", "15Min", "1H", "1D"}


@router.get("/portfolio/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    period: str = "1M", timeframe: str | None = None
) -> PortfolioHistoryResponse:
    if period not in _ALLOWED_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {sorted(_ALLOWED_PERIODS)}",
        )
    if timeframe is not None and timeframe not in _ALLOWED_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"timeframe must be one of {sorted(_ALLOWED_TIMEFRAMES)}",
        )
    try:
        data = await asyncio.to_thread(alpaca.get_portfolio_history, period, timeframe)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return PortfolioHistoryResponse(**data)


@router.post("/orders", response_model=OrderResponse)
async def place_order(req: ExecuteOrderRequest, session: AsyncSession = Depends(get_session)) -> OrderResponse:
    verdict = await vrepo.get_by_id(req.verdict_id, session)
    if verdict is None:
        raise HTTPException(status_code=404, detail=f"Verdict {req.verdict_id} not found")
    if verdict.action == "HOLD":
        raise HTTPException(
            status_code=400, detail="Cannot execute a HOLD verdict — no order to place"
        )

    side = "buy" if verdict.action == "BUY" else "sell"

    # Position sizing: notional = equity * BULL_POSITION_SIZE_PCT / 100
    try:
        account = await asyncio.to_thread(alpaca.get_account)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    notional = round(account["equity"] * settings.bull_position_size_pct / 100, 2)
    if notional <= 0:
        raise HTTPException(status_code=400, detail=f"Computed notional ${notional} is non-positive")

    alpaca_resp = await asyncio.to_thread(alpaca.place_order, verdict.ticker, side, notional)

    order = Order(
        verdict_id=verdict.id,
        alpaca_order_id=alpaca_resp["alpaca_order_id"],
        ticker=verdict.ticker,
        side=side,
        qty=alpaca_resp.get("qty") or None,
        notional=alpaca_resp.get("notional") or notional,
        status=alpaca_resp["status"],
        submitted_at=alpaca_resp["submitted_at"] or now_utc(),
        filled_avg_price=alpaca_resp.get("filled_avg_price") or None,
    )
    persisted = await orepo.insert(order, session)
    return _order_to_response(persisted)


@router.delete("/positions/{symbol}")
async def close_position(symbol: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    try:
        resp = await asyncio.to_thread(alpaca.close_position, symbol)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    # Persist the close-order so the trade journal sees both legs of the round trip.
    order = Order(
        verdict_id=None,
        alpaca_order_id=resp["alpaca_order_id"],
        ticker=symbol,
        side=resp.get("side") or "sell",
        qty=None,
        notional=None,
        status=resp["status"],
        submitted_at=resp["submitted_at"] or now_utc(),
        filled_avg_price=None,
    )
    await orepo.insert(order, session)
    return resp
