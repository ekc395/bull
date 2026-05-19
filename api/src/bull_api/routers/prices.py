"""GET /prices/{ticker} — OHLCV + indicators + S/R for the chart."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..tools.indicators import compute_indicators
from ..tools.prices import get_price_history
from ..tools.support_resistance import find_support_resistance

router = APIRouter()

CHART_BARS_DEFAULT = 252  # ~1 year of trading days


@router.get("/prices/{ticker}")
async def get_prices(
    ticker: str,
    bars: int = Query(CHART_BARS_DEFAULT, ge=20, le=400),
) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        df = await asyncio.to_thread(get_price_history, ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    indicators, sr = await asyncio.gather(
        asyncio.to_thread(compute_indicators, df),
        asyncio.to_thread(find_support_resistance, df),
    )

    tail = df.tail(bars)
    chart_bars = [
        {
            "date": ts.date().isoformat(),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        }
        for ts, row in tail.iterrows()
    ]

    return {
        "ticker": ticker,
        "current_price": round(float(df["Close"].iloc[-1]), 2),
        "bars": chart_bars,
        "indicators": indicators,
        "support_resistance": sr,
    }
