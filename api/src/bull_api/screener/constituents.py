"""S&P 500 constituent universe: scrape Wikipedia, cache in SQLite, refresh weekly.

Wikipedia keeps the canonical list at /wiki/List_of_S%26P_500_companies in a
table with id="constituents". Columns we care about: Symbol, Security (name),
GICS Sector. Yahoo ticker convention swaps dots for dashes (BRK.B -> BRK-B), so
we normalize before storing.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SP500Constituent
from ..time import now_utc

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
REFRESH_INTERVAL = timedelta(days=7)


@dataclass(frozen=True)
class Constituent:
    symbol: str
    company_name: str
    sector: str


def normalize_symbol(raw: str) -> str:
    """Yahoo ticker convention: BRK.B -> BRK-B, BF.B -> BF-B."""
    return raw.strip().replace(".", "-").upper()


def parse_constituents_html(html: str) -> list[Constituent]:
    """Extract the constituents table. Raises ValueError if the page shape changed."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="constituents")
    if table is None:
        raise ValueError("Wikipedia constituents table not found")

    out: list[Constituent] = []
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody is not None else []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue  # header row has no <td>s
        symbol = normalize_symbol(cells[0].get_text(strip=True))
        company = cells[1].get_text(strip=True)
        sector = cells[2].get_text(strip=True)
        if not symbol or not company:
            continue
        out.append(Constituent(symbol=symbol, company_name=company, sector=sector))
    if len(out) < 400:
        raise ValueError(
            f"Expected ~500 S&P constituents from Wikipedia, parsed {len(out)} — "
            "page structure may have changed"
        )
    return out


async def fetch_sp500_from_wikipedia() -> list[Constituent]:
    """Network fetch + parse. Surfaces httpx errors for the caller to handle."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(
            WIKIPEDIA_URL,
            headers={"User-Agent": "bull-screener/0.1 (research)"},
        )
        resp.raise_for_status()
    return parse_constituents_html(resp.text)


async def _is_cache_stale(session: AsyncSession) -> bool:
    stmt = select(SP500Constituent.refreshed_at).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return True
    if row.tzinfo is None:
        row = row.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - row > REFRESH_INTERVAL


async def get_constituents(
    session: AsyncSession, *, force_refresh: bool = False
) -> list[Constituent]:
    """Return the cached universe, refreshing from Wikipedia if stale or empty.

    Refresh is all-or-nothing: replace the entire table inside one transaction so
    a partial scrape can't leave the DB in a mixed state.
    """
    if not force_refresh and not await _is_cache_stale(session):
        rows = (await session.execute(select(SP500Constituent))).scalars().all()
        return [
            Constituent(symbol=r.symbol, company_name=r.company_name, sector=r.sector)
            for r in rows
        ]

    fresh = await fetch_sp500_from_wikipedia()
    now = now_utc()
    await session.execute(delete(SP500Constituent))
    session.add_all(
        SP500Constituent(
            symbol=c.symbol,
            company_name=c.company_name,
            sector=c.sector,
            refreshed_at=now,
        )
        for c in fresh
    )
    await session.commit()
    return fresh
