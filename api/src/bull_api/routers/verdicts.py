"""GET /verdicts and GET /verdicts/{id}."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..repos import verdicts as vrepo
from ..schemas import VerdictResponse
from . import verdict_to_response

router = APIRouter()


@router.get("/verdicts", response_model=list[VerdictResponse])
async def list_verdicts(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[VerdictResponse]:
    rows = await vrepo.list_recent(limit, session)
    return [verdict_to_response(v) for v in rows]


@router.get("/verdicts/{verdict_id}", response_model=VerdictResponse)
async def get_verdict(verdict_id: int, session: AsyncSession = Depends(get_session)) -> VerdictResponse:
    v = await vrepo.get_by_id(verdict_id, session)
    if v is None:
        raise HTTPException(status_code=404, detail=f"Verdict {verdict_id} not found")
    return verdict_to_response(v)
