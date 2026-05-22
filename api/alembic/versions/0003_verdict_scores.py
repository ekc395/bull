"""verdict_scores table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-22

Adds verdict_scores: one row per (verdict, trading-day horizon) recording the
realized return after the verdict's created_at. Populated by the scoring job
(bull_api.scoring); enables the verdict-vs-realized hit-rate feedback loop.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verdict_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "verdict_id",
            sa.Integer(),
            sa.ForeignKey("verdicts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("entry_close", sa.Float(), nullable=False),
        sa.Column("exit_close", sa.Float(), nullable=False),
        sa.Column("realized_return_pct", sa.Float(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("verdict_id", "horizon_days", name="uq_verdict_horizon"),
    )


def downgrade() -> None:
    op.drop_table("verdict_scores")
