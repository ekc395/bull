"""drop deeper/escalation columns from verdicts

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-24

Opus is now the sole analysis model — the standard/deeper split and the
advisory escalation layer are gone. Drop the four columns that backed them:
`depth`, `parent_verdict_id`, `escalation_recommended`, `escalation_reasons_json`.

SQLite cannot drop a column referenced by a foreign key in-place, so we use
batch_alter_table to rebuild the table. Postgres handles DROP COLUMN directly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DROPPED = (
    "escalation_reasons_json",
    "escalation_recommended",
    "parent_verdict_id",
    "depth",
)


def upgrade() -> None:
    with op.batch_alter_table("verdicts") as batch:
        for col in _DROPPED:
            batch.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("verdicts") as batch:
        batch.add_column(
            sa.Column(
                "depth",
                sa.String(length=16),
                nullable=False,
                server_default="standard",
            )
        )
        batch.add_column(
            sa.Column(
                "parent_verdict_id",
                sa.Integer(),
                sa.ForeignKey("verdicts.id"),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "escalation_recommended",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column(
                "escalation_reasons_json",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )
