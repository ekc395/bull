"""Alpaca paper-trading endpoints: account, positions, orders."""

from fastapi import APIRouter

from ..schemas import AccountResponse, ExecuteOrderRequest, OrderResponse, PositionResponse

router = APIRouter()


@router.get("/account", response_model=AccountResponse)
async def get_account() -> AccountResponse:
    raise NotImplementedError


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions() -> list[PositionResponse]:
    raise NotImplementedError


@router.post("/orders", response_model=OrderResponse)
async def place_order(req: ExecuteOrderRequest) -> OrderResponse:
    raise NotImplementedError


@router.delete("/positions/{symbol}")
async def close_position(symbol: str) -> dict:
    raise NotImplementedError
