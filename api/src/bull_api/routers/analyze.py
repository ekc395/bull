"""POST /analyze and POST /verdicts/{id}/deepen."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent import analyze_ticker, deepen_verdict
from ..db import get_session
from ..schemas import AnalyzeRequest, VerdictResponse
from . import verdict_to_response

router = APIRouter()


@router.post("/analyze", response_model=VerdictResponse)
async def analyze(req: AnalyzeRequest, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    if not req.ticker.strip():
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        verdict = await analyze_ticker(req.ticker, session, force=req.force)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return verdict_to_response(verdict)


@router.post("/verdicts/{verdict_id}/deepen", response_model=VerdictResponse)
async def deepen(verdict_id: int, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    try:
        verdict = await deepen_verdict(verdict_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return verdict_to_response(verdict)
