"""POST /screener/preview, POST /screener/run."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent import analyze_ticker
from ..db import get_session
from ..schemas import (
    ScreenerCandidate,
    ScreenerPreviewResponse,
    ScreenerRunRequest,
    ScreenerRunResponse,
)
from ..screener.scan import MAX_CANDIDATES, run_preview
from . import verdict_to_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screener", tags=["screener"])


@router.post("/preview", response_model=ScreenerPreviewResponse)
async def preview(session: AsyncSession = Depends(get_session)) -> ScreenerPreviewResponse:
    """Free pre-filter pass over the S&P 500. No LLM calls."""
    try:
        result = await run_preview(session)
    except Exception as e:
        logger.exception("screener preview failed")
        raise HTTPException(status_code=502, detail=f"Screener failed: {e}") from e

    return ScreenerPreviewResponse(
        candidates=[
            ScreenerCandidate(
                symbol=c.symbol,
                company_name=c.company_name,
                sector=c.sector,
                close=c.close,
                rsi_14=c.rsi_14,
                macd_hist=c.macd_hist,
                sma_50=c.sma_50,
                sma_200=c.sma_200,
                volume_current=c.volume_current,
                volume_20d_avg=c.volume_20d_avg,
            )
            for c in result.candidates
        ],
        universe_size=result.universe_size,
        filtered_out=result.filtered_out,
        overflowed=result.overflowed,
        estimated_cost_usd=result.estimated_cost_usd,
        model=result.model,
        errors=result.errors,
    )


@router.post("/run", response_model=ScreenerRunResponse)
async def run(
    req: ScreenerRunRequest, session: AsyncSession = Depends(get_session)
) -> ScreenerRunResponse:
    """Paid pass: run the Opus analysis on the user-confirmed subset of candidates.

    Sequential by design — keeps spend predictable and stays polite with the
    Anthropic API. Same-day re-runs hit the existing verdict cache for free.
    """
    if len(req.tickers) > MAX_CANDIDATES:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_CANDIDATES} tickers per run (got {len(req.tickers)})",
        )

    verdicts = []
    errors: list[str] = []
    for raw in req.tickers:
        ticker = raw.strip().upper()
        if not ticker:
            continue
        try:
            verdict = await analyze_ticker(ticker, session)
        except Exception as e:
            logger.warning("screener analysis failed for %s: %s", ticker, e)
            errors.append(f"{ticker}: {e}")
            continue
        verdicts.append(verdict_to_response(verdict))

    return ScreenerRunResponse(verdicts=verdicts, errors=errors)
