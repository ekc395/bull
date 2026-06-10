"""POST /analyze."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent import InsufficientCreditsError, analyze_ticker
from ..config import settings
from ..db import SessionLocal, get_session
from ..maintenance import prune_old_verdicts
from ..repos import verdicts as vrepo
from ..schemas import (
    AnalyzeRequest,
    VerdictResponse,
    WatchlistAnalyzeItem,
    WatchlistAnalyzeResponse,
    WatchlistItemResponse,
    WatchlistResponse,
)
from ..scoring import score_pending_verdicts
from ..time import trading_day
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


def _watchlist_symbols() -> list[str]:
    return [t.strip().upper() for t in settings.bull_watchlist.split(",") if t.strip()]


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(session: AsyncSession = Depends(get_session)) -> WatchlistResponse:
    """The configured watchlist + each ticker's latest short-mode verdict."""
    today = trading_day()
    items: list[WatchlistItemResponse] = []
    for ticker in _watchlist_symbols():
        v = await vrepo.latest_for(ticker, session, timeframe="short")
        items.append(
            WatchlistItemResponse(
                ticker=ticker,
                verdict_id=v.id if v else None,
                action=v.action if v else None,  # type: ignore[arg-type]
                confidence=v.confidence if v else None,
                candidate_action=v.candidate_action if v else None,
                active_strategy=(v.algo_json or {}).get("active_strategy") if v else None,
                created_at=v.created_at if v else None,
                fresh_today=v is not None and trading_day(v.created_at) == today,
            )
        )
    return WatchlistResponse(active_strategy=settings.bull_active_strategy, items=items)


@router.post("/watchlist/analyze", response_model=WatchlistAnalyzeResponse)
async def analyze_watchlist(
    session: AsyncSession = Depends(get_session),
) -> WatchlistAnalyzeResponse:
    """Batch short-mode run over the watchlist — the tournament's forward feed.

    Manual trigger only (each uncached ticker is a paid Opus call; no cron by
    design). Cache-respecting: a re-run on the same trading day costs nothing,
    and `llm_calls_made` reports exactly how many paid calls happened. One
    ticker failing doesn't abort the rest; exhausted API credits do (every
    remaining ticker would fail identically).
    """
    results: list[WatchlistAnalyzeItem] = []
    llm_calls = 0
    today = trading_day()
    for ticker in _watchlist_symbols():
        cached = await vrepo.get_for_today(ticker, today, session, timeframe="short")
        try:
            verdict = cached or await analyze_ticker(ticker, session, timeframe="short")
        except InsufficientCreditsError as e:
            results.append(WatchlistAnalyzeItem(ticker=ticker, error=str(e)))
            break
        except Exception as e:
            logger.exception("watchlist analyze failed for %s", ticker)
            results.append(WatchlistAnalyzeItem(ticker=ticker, error=str(e)))
            continue
        if cached is None:
            llm_calls += 1
        results.append(
            WatchlistAnalyzeItem(
                ticker=ticker,
                cached=cached is not None,
                verdict_id=verdict.id,
                action=verdict.action,  # type: ignore[arg-type]
                confidence=verdict.confidence,
                candidate_action=verdict.candidate_action,
            )
        )
    asyncio.create_task(_score_in_background())
    return WatchlistAnalyzeResponse(results=results, llm_calls_made=llm_calls)
