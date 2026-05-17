"""Order repository: persist Alpaca submissions, list history."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Order


async def insert(order: Order, session: AsyncSession) -> Order:
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def list_recent(limit: int, session: AsyncSession) -> list[Order]:
    stmt = select(Order).order_by(desc(Order.created_at)).limit(limit)
    return list((await session.execute(stmt)).scalars().all())
