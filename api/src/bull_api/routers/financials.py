"""GET /financials/{ticker} — multi-year revenue / net income / EBITDA series
for the Financials charts. yfinance income statement, cached 24h in-tool.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from ..tools.financials import get_financials

router = APIRouter()


@router.get("/financials/{ticker}")
async def get_financials_endpoint(ticker: str) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        data = await asyncio.to_thread(get_financials, ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ticker": ticker, **data}
