"""Background maintenance: soft-prune old verdict payloads.

Verdicts are kept forever so `verdict_scores` and historical links stay valid,
but the bulky JSON fields (`report_json`, `raw_response_json`,
`facts_bundle_json`, `key_levels_json`) are replaced with placeholders once a
verdict is older than `MAX_AGE_DAYS`. This keeps DB size bounded under heavy use
while preserving the row, headline, action, and confidence.

The pruner is idempotent: it skips rows that already have an empty
`raw_response_json` AND empty `facts_bundle_json`, the sentinel left by the
placeholder writer.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Verdict
from .time import now_utc

MAX_AGE_DAYS = 365

ARCHIVED_NOTE = (
    f"(archived — full report pruned after {MAX_AGE_DAYS} days to keep the DB small. "
    "Headline, action, and confidence are preserved.)"
)

_ARCHIVED_REPORT_TEMPLATE = {
    "technical": ARCHIVED_NOTE,
    "fundamentals_and_supply_chain": ARCHIVED_NOTE,
    "news_sentiment": ARCHIVED_NOTE,
    "risks": ARCHIVED_NOTE,
    "reasoning": ARCHIVED_NOTE,
}


async def prune_old_verdicts(session: AsyncSession, *, max_age_days: int = MAX_AGE_DAYS) -> int:
    """Soft-prune verdicts older than `max_age_days`. Returns count of rows pruned."""
    cutoff = now_utc() - timedelta(days=max_age_days)
    result = await session.execute(select(Verdict).where(Verdict.created_at < cutoff))
    rows = result.scalars().all()

    pruned = 0
    for v in rows:
        if not v.raw_response_json and not v.facts_bundle_json:
            continue
        v.report_json = dict(_ARCHIVED_REPORT_TEMPLATE)
        v.key_levels_json = {"support": [], "resistance": []}
        v.raw_response_json = {}
        v.facts_bundle_json = {}
        pruned += 1

    if pruned:
        await session.commit()
    return pruned
