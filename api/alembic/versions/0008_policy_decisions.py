"""policy_decisions table

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-07

Adds policy_decisions: one row per execution-time gating/sizing decision the
learning layer (policy/gate.py) makes for a verdict. Persisting decisions lets
the policy itself be forward-tested against realized outcomes the same way
verdict_scores evaluates the model. `policy_version` tags the rule revision so
decisions remain comparable across policy changes. See plan.md → Phase 3.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "verdict_id",
            sa.Integer(),
            sa.ForeignKey("verdicts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("act", sa.Boolean(), nullable=False),
        sa.Column("size_pct", sa.Float(), nullable=False),
        sa.Column("rationale", sa.String(length=512), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("policy_decisions")
