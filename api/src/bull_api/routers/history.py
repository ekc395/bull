"""GET /orders — paginated paper-order history."""

from fastapi import APIRouter

from ..schemas import OrderResponse

router = APIRouter()


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(limit: int = 50) -> list[OrderResponse]:
    raise NotImplementedError
