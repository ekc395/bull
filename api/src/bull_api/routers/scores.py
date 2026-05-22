"""GET /scores/summary and POST /scores/run.

Surfaces the backtest feedback loop. Hit rate breakdown is computed on the
fly from VerdictScore rows so the win/loss threshold is a query parameter,
not a stored field.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..scoring import score_pending_verdicts, summary

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("/summary")
async def get_summary(
    threshold: float = Query(0.0, ge=0.0, le=50.0, description="Hit threshold in % return"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await summary(session, threshold=threshold)


@router.post("/run")
async def run_scoring(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    return await score_pending_verdicts(session)
