"""Agent: deterministic tool fetch + single-shot synthesis.

Two entry points:
- analyze_ticker(ticker, session, force=False) → always Sonnet, NEVER calls Opus.
  Computes `escalation_recommended` + reasons advisorily.
- deepen_verdict(verdict_id, session) → user-initiated Opus pass on the same facts bundle.

See plan.md → Backend → agent.py for the full flow.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Verdict


async def analyze_ticker(
    ticker: str, session: AsyncSession, *, force: bool = False
) -> Verdict:
    raise NotImplementedError


async def deepen_verdict(verdict_id: int, session: AsyncSession) -> Verdict:
    """User-triggered Opus pass. Reuses the parent verdict's facts_bundle_json — no re-fetching."""
    raise NotImplementedError
