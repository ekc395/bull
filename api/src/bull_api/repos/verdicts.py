"""Verdict repository: persistence + (ticker, trading-day) cache lookup."""

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Verdict
from ..time import trading_day_bounds


async def get_for_today(ticker: str, on: date, session: AsyncSession) -> Verdict | None:
    """Most recent Verdict for `ticker` whose trading day is `on` (US/Eastern)."""
    start, end = trading_day_bounds(on)
    stmt = (
        select(Verdict)
        .where(
            Verdict.ticker == ticker.upper(),
            Verdict.created_at >= start,
            Verdict.created_at < end,
        )
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
