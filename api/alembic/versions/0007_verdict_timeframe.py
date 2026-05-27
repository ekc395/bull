"""add timeframe column to verdicts

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-27

Holding-period the user selects in the UI (short | medium | long). Drives the
prompt variant and tool windows in `agent.py`. Backfills existing rows to
"medium" — the prior agent was swing-positioned (closer to "short"), but
"medium" is the new product default and avoids re-labeling history.

Composite index `(ticker, timeframe, created_at desc)` covers the per-day
cache lookup which now filters by (ticker, trading_day, timeframe).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("verdicts") as batch:
        batch.add_column(
            sa.Column(
                "timeframe",
                sa.String(length=8),
                nullable=False,
                server_default="medium",
            )
        )
    op.create_index(
        "ix_verdicts_ticker_timeframe_created_at",
        "verdicts",
        ["ticker", "timeframe", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_verdicts_ticker_timeframe_created_at", table_name="verdicts")
    with op.batch_alter_table("verdicts") as batch:
        batch.drop_column("timeframe")
