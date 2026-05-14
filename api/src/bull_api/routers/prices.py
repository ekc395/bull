"""GET /prices/{ticker} — OHLCV + indicators for the chart."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/prices/{ticker}")
async def get_prices(ticker: str) -> dict:
    raise NotImplementedError
