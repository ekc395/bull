"""Shared helpers for the router modules."""

from ..models import Verdict
from ..schemas import VerdictResponse


def verdict_to_response(v: Verdict) -> VerdictResponse:
    """Map a Verdict ORM row onto the public response schema."""
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
        depth=v.depth,  # type: ignore[arg-type]
        parent_verdict_id=v.parent_verdict_id,
        escalation_recommended=v.escalation_recommended,
        escalation_reasons=v.escalation_reasons_json,
    )
