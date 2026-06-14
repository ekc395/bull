"""drop the medium timeframe

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-13

The product now offers only two holding periods — short and long. "medium" is
removed everywhere in the app; this migration purges its data and re-points the
column default.

Existing medium verdicts are DELETED (not relabeled — relabeling history would
misrepresent which prompt/lens actually produced them). Their dependent rows go
first to satisfy the foreign keys: `policy_decisions` and `verdict_scores` are
deleted outright, while `orders` are kept (paper-trade history) with their
`verdict_id` set NULL (the column is already nullable). Finally the column
`server_default` moves from "medium" to "short", the new product default.

downgrade() only restores the old server_default — the deleted rows are gone.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEDIUM_IDS = "SELECT id FROM verdicts WHERE timeframe = 'medium'"


def upgrade() -> None:
    op.execute(f"DELETE FROM policy_decisions WHERE verdict_id IN ({_MEDIUM_IDS})")
    op.execute(f"DELETE FROM verdict_scores WHERE verdict_id IN ({_MEDIUM_IDS})")
    # Preserve paper-trade rows; just sever the link to the doomed verdict.
    op.execute(f"UPDATE orders SET verdict_id = NULL WHERE verdict_id IN ({_MEDIUM_IDS})")
    op.execute("DELETE FROM verdicts WHERE timeframe = 'medium'")

    with op.batch_alter_table("verdicts") as batch:
        batch.alter_column(
            "timeframe",
            existing_type=sa.String(length=8),
            existing_nullable=False,
            server_default="short",
        )


def downgrade() -> None:
    # Restores only the prior default; the deleted medium rows are not recoverable.
    with op.batch_alter_table("verdicts") as batch:
        batch.alter_column(
            "timeframe",
            existing_type=sa.String(length=8),
            existing_nullable=False,
            server_default="medium",
        )
