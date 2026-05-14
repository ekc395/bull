"""Verdict repository: persistence + (ticker, date) cache lookup."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Verdict


async def get_standard_for_today(ticker: str, on: date, session: AsyncSession) -> Verdict | None:
    raise NotImplementedError


async def get_by_id(verdict_id: int, session: AsyncSession) -> Verdict | None:
    raise NotImplementedError


async def list_recent(limit: int, session: AsyncSession) -> list[Verdict]:
    raise NotImplementedError


async def insert(verdict: Verdict, session: AsyncSession) -> Verdict:
    raise NotImplementedError


async def find_deeper_child(parent_id: int, session: AsyncSession) -> Verdict | None:
    """For idempotency of the deepen endpoint."""
    raise NotImplementedError
