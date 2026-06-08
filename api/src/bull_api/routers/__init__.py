"""Shared helpers for the router modules."""

from ..models import Verdict
from ..policy.gate import PolicyDecision
from ..schemas import PolicyDecisionResponse, VerdictResponse


def verdict_to_response(
    v: Verdict, policy: PolicyDecision | None = None
) -> VerdictResponse:
    """Map a Verdict ORM row onto the public response schema.

    `policy` is the optional advisory gating/sizing decision (Phase 3); when
    omitted the response's `policy` field stays None.
    """
    return VerdictResponse(
        id=v.id,
        ticker=v.ticker,
        action=v.action,  # type: ignore[arg-type]
        confidence=v.confidence,
        headline=v.headline,
        report=v.report_json,  # type: ignore[arg-type]
        key_levels=v.key_levels_json,  # type: ignore[arg-type]
        created_at=v.created_at,
        model_used=v.model_used,
        timeframe=v.timeframe,  # type: ignore[arg-type]
        policy=(
            PolicyDecisionResponse(
                act=policy.act,
                size_pct=policy.size_pct,
                rationale=policy.rationale,
                policy_version=policy.policy_version,
            )
            if policy is not None
            else None
        ),
    )
