"""tz-aware timestamps

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-17

Switches verdicts.created_at, orders.submitted_at, orders.created_at, and
tickers.last_analyzed_at to TIMESTAMP WITH TIME ZONE so the verdict cache can
key off a US/Eastern trading day computed from UTC instants. SQLite stores
datetimes as text either way, so this is effectively a no-op there; on Postgres
it produces `timestamptz` columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AWARE = [
    ("verdicts", "created_at", False),
    ("orders", "submitted_at", False),
    ("orders", "created_at", False),
    ("tickers", "last_analyzed_at", True),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite has no native timestamptz; existing DATETIME columns already store
        # ISO strings, which SQLAlchemy reads back as tz-aware once the column is
        # declared DateTime(timezone=True) at the ORM layer. Nothing to alter.
        return
    for table, col, nullable in _AWARE:
        op.alter_column(
            table,
            col,
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=nullable,
            postgresql_using=f"{col} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    for table, col, nullable in _AWARE:
        op.alter_column(
            table,
            col,
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=nullable,
        )
