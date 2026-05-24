"""Verdict repository: persistence + (ticker, trading-day) cache lookup."""

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Verdict
from ..time import trading_day_bounds


async def get_for_today(ticker: str, on: date, session: AsyncSession) -> Verdict | None:
    """Most recent Verdict for `ticker` whose trading day is `on` (US/Eastern).

    Depth-agnostic — if a row has been upgraded to `deeper` in place, we still
    return it so the analyze cache short-circuits on the upgraded data.
    Excludes legacy `deeper` child rows (which carry a parent_verdict_id).
    """
    start, end = trading_day_bounds(on)
    stmt = (
        select(Verdict)
        .where(
            Verdict.ticker == ticker.upper(),
            Verdict.parent_verdict_id.is_(None),
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
    # Hide legacy `deeper` children (pre-update-in-place rows) from the dashboard.
    # New deepens mutate the original row, so anything with a parent_verdict_id
    # is a duplicate of an older standard row already listed.
    stmt = (
        select(Verdict)
        .where(Verdict.parent_verdict_id.is_(None))
        .order_by(desc(Verdict.created_at))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def insert(verdict: Verdict, session: AsyncSession) -> Verdict:
    session.add(verdict)
    await session.commit()
    await session.refresh(verdict)
    return verdict


async def save(verdict: Verdict, session: AsyncSession) -> Verdict:
    """Commit pending mutations on an already-tracked Verdict row."""
    await session.commit()
    await session.refresh(verdict)
    return verdict
