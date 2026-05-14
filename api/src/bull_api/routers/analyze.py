"""POST /analyze and POST /verdicts/{id}/deepen."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent import analyze_ticker, deepen_verdict
from ..db import get_session
from ..schemas import AnalyzeRequest, VerdictResponse

router = APIRouter()


@router.post("/analyze", response_model=VerdictResponse)
async def analyze(req: AnalyzeRequest, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    raise NotImplementedError


@router.post("/verdicts/{verdict_id}/deepen", response_model=VerdictResponse)
async def deepen(verdict_id: int, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    raise NotImplementedError
