"""GET /fundamentals/{ticker} — company name, sector, market cap, P/E, etc.

Surfaces the same data the agent already fetches internally so the web app can
render the TradingView-style header (company name, sector breadcrumb) and key
facts. Free sources (Finnhub / yfinance / Alpha Vantage), cached 24h in-tool.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from ..tools.fundamentals import get_fundamentals

router = APIRouter()


@router.get("/fundamentals/{ticker}")
async def get_fundamentals_endpoint(ticker: str) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        data = await asyncio.to_thread(get_fundamentals, ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ticker": ticker, **data}
