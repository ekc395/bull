"""Order repository: persist Alpaca submissions, list history."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Order


async def insert(order: Order, session: AsyncSession) -> Order:
    raise NotImplementedError


async def list_recent(limit: int, session: AsyncSession) -> list[Order]:
    raise NotImplementedError
