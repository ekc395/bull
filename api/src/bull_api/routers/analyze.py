"""POST /analyze."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent import InsufficientCreditsError, analyze_ticker
from ..db import SessionLocal, get_session
from ..maintenance import prune_old_verdicts
from ..schemas import AnalyzeRequest, VerdictResponse
from ..scoring import score_pending_verdicts
from . import verdict_to_response

logger = logging.getLogger(__name__)
router = APIRouter()

# Module-level gate so the prune scan runs at most once per day, not on every
# /analyze. Resets on restart, which is fine — first request after restart will
# run it again.
_PRUNE_INTERVAL = timedelta(days=1)
_last_prune_at: datetime | None = None


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


async def _prune_in_background() -> None:
    """Soft-prune verdicts older than 365 days. Fire-and-forget, rate-gated to
    once per day. Same swallow-and-log discipline as scoring.
    """
    global _last_prune_at
    now = datetime.now(timezone.utc)
    if _last_prune_at is not None and (now - _last_prune_at) < _PRUNE_INTERVAL:
        return
    _last_prune_at = now
    try:
        async with SessionLocal() as session:
            pruned = await prune_old_verdicts(session)
            if pruned:
                logger.info("background prune archived %d old verdict(s)", pruned)
    except Exception:
        logger.exception("background prune failed")


@router.post("/analyze", response_model=VerdictResponse)
async def analyze(req: AnalyzeRequest, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    if not req.ticker.strip():
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        verdict = await analyze_ticker(
            req.ticker, session, force=req.force, timeframe=req.timeframe
        )
    except InsufficientCreditsError as e:
        raise HTTPException(status_code=402, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    asyncio.create_task(_score_in_background())
    asyncio.create_task(_prune_in_background())
    return verdict_to_response(verdict)
