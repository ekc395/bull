"""GET /news/{ticker} — recent news feed for the analysis page."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..tools.news import get_recent_news

router = APIRouter()


@router.get("/news/{ticker}")
async def get_news(
    ticker: str,
    days: int = Query(7, ge=1, le=30),
) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    items = await asyncio.to_thread(get_recent_news, ticker, days)
    return {"ticker": ticker, "items": items}
