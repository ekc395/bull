"""Verdict repository: persistence + (ticker, trading-day) cache lookup."""

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Verdict
from ..time import trading_day_bounds


async def get_for_today(
    ticker: str, on: date, session: AsyncSession, *, timeframe: str = "short"
) -> Verdict | None:
    """Most recent Verdict for `(ticker, timeframe)` whose trading day is `on` (US/Eastern).

    Same ticker on the same NYSE session under a different holding period is a
    cache miss — each timeframe gets its own daily slot.
    """
    start, end = trading_day_bounds(on)
    stmt = (
        select(Verdict)
        .where(
            Verdict.ticker == ticker.upper(),
            Verdict.timeframe == timeframe,
            Verdict.created_at >= start,
            Verdict.created_at < end,
        )
        .order_by(desc(Verdict.created_at))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def latest_for(
    ticker: str, session: AsyncSession, *, timeframe: str
) -> Verdict | None:
    """Most recent Verdict for `(ticker, timeframe)` regardless of trading day.
    Watchlist summaries use this; the daily cache lookup is `get_for_today`."""
    stmt = (
        select(Verdict)
        .where(Verdict.ticker == ticker.upper(), Verdict.timeframe == timeframe)
        .order_by(desc(Verdict.created_at))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_id(verdict_id: int, session: AsyncSession) -> Verdict | None:
    return await session.get(Verdict, verdict_id)


async def list_recent(limit: int, session: AsyncSession) -> list[Verdict]:
    stmt = (
        select(Verdict)
        .order_by(desc(Verdict.created_at))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def insert(verdict: Verdict, session: AsyncSession) -> Verdict:
    session.add(verdict)
    await session.commit()
    await session.refresh(verdict)
    return verdict
