"""GET /orders — paginated paper-order history (from our local DB)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Order
from ..repos import orders as orepo
from ..schemas import OrderResponse

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


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[OrderResponse]:
    rows = await orepo.list_recent(limit, session)
    return [_order_to_response(o) for o in rows]
