"""POST /analyze and POST /verdicts/{id}/deepen."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent import analyze_ticker, deepen_verdict
from ..db import SessionLocal, get_session
from ..schemas import AnalyzeRequest, VerdictResponse
from ..scoring import score_pending_verdicts
from . import verdict_to_response

logger = logging.getLogger(__name__)
router = APIRouter()


async def _score_in_background() -> None:
    """Opportunistic scoring of any verdicts past horizon. Fire-and-forget;
    runs in its own session so the request handler's session can close. Any
    exception is swallowed (logged) — scoring failures must never affect the
    /analyze response.
    """
    try:
        async with SessionLocal() as session:
            counts = await score_pending_verdicts(session)
            if counts["scores_inserted"]:
                logger.info(
                    "background scoring inserted %d row(s) across %d verdict(s)",
                    counts["scores_inserted"],
                    counts["verdicts_processed"],
                )
    except Exception:
        logger.exception("background scoring failed")


@router.post("/analyze", response_model=VerdictResponse)
async def analyze(req: AnalyzeRequest, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    if not req.ticker.strip():
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        verdict = await analyze_ticker(req.ticker, session, force=req.force)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    asyncio.create_task(_score_in_background())
    return verdict_to_response(verdict)


@router.post("/verdicts/{verdict_id}/deepen", response_model=VerdictResponse)
async def deepen(verdict_id: int, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    try:
        verdict = await deepen_verdict(verdict_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    asyncio.create_task(_score_in_background())
    return verdict_to_response(verdict)
