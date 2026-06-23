"""GET /screen — run the free strategy screener over the liquid universe.

No LLM, no DB writes. First call of a trading day is slow (yfinance fetch per
universe name, ~1-3 min at size 100); same-day re-runs hit the per-day caches.
The CLI (`python -m bull_api.screen`) is the same engine with a table printer.
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..screen import MAX_UNIVERSE_SIZE, run_screen

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/screen")
async def screen(
    size: int = Query(default=None, ge=1, le=MAX_UNIVERSE_SIZE),
    tickers: str | None = Query(default=None, description="comma-separated manual universe"),
) -> dict[str, Any]:
    manual = [t.strip() for t in tickers.split(",") if t.strip()] if tickers else None
    try:
        return await asyncio.to_thread(run_screen, size, manual)
    except Exception as e:  # Yahoo screener hiccups shouldn't 500 opaquely
        # Log full detail server-side; never echo `e` to the client — a
        # downstream httpx error can carry the data-source URL incl. its API key.
        logger.exception("screen failed (size=%s, tickers=%s)", size, tickers)
        raise HTTPException(status_code=502, detail="screener data source unavailable") from e
