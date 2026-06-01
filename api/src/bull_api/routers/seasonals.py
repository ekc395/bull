"""GET /seasonals/{ticker} — average monthly return over ~10 years.
yfinance monthly closes, cached 24h in-tool. Descriptive, not a forecast.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from ..tools.seasonals import get_seasonals

router = APIRouter()


@router.get("/seasonals/{ticker}")
async def get_seasonals_endpoint(ticker: str) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        data = await asyncio.to_thread(get_seasonals, ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ticker": ticker, **data}
