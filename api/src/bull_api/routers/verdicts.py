"""GET /verdicts and GET /verdicts/{id}."""

from fastapi import APIRouter

from ..schemas import VerdictResponse

router = APIRouter()


@router.get("/verdicts", response_model=list[VerdictResponse])
async def list_verdicts(limit: int = 50) -> list[VerdictResponse]:
    raise NotImplementedError


@router.get("/verdicts/{verdict_id}", response_model=VerdictResponse)
async def get_verdict(verdict_id: int) -> VerdictResponse:
    raise NotImplementedError
