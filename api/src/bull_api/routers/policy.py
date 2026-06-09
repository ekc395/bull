"""GET /policy/calibration — Phase-2 calibration & edge analysis.

Surfaces the outcome-feedback analysis: hit rate + realized returns bucketed by
confidence band (calibration) and by setup context features (edge), computed on
the fly from VerdictScore rows. Threshold and min-sample guard are query
parameters so they stay runtime knobs, not stored fields.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..policy.analysis import DEFAULT_MIN_N, report

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/calibration")
async def get_calibration(
    threshold: float = Query(0.0, ge=0.0, le=50.0, description="Hit threshold in % return"),
    min_n: int = Query(
        DEFAULT_MIN_N, ge=1, le=1000, description="Min samples before a bucket is trusted"
    ),
    model: str | None = Query(
        None,
        description="Model regime to analyze; defaults to pooling every model, "
        "'current' for the active BULL_MODEL, or a model id to slice one",
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await report(session, threshold=threshold, min_n=min_n, model=model)
