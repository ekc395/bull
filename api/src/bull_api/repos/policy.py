"""Policy-decision repository: persist gating/sizing decisions.

Maps the pure `gate.PolicyDecision` dataclass onto the `PolicyDecision` ORM row
and commits it. Isolating the ORM import here keeps the gate logic free of the
ORM-name collision (the dataclass and the model share a name by design — they
are the same concept in two layers).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PolicyDecision as PolicyDecisionRow
from ..policy.gate import PolicyDecision


async def insert_decision(
    decision: PolicyDecision, verdict_id: int, session: AsyncSession
) -> PolicyDecisionRow:
    row = PolicyDecisionRow(
        verdict_id=verdict_id,
        act=decision.act,
        size_pct=decision.size_pct,
        rationale=decision.rationale,
        policy_version=decision.policy_version,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
