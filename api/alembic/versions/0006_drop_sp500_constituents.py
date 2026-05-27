"""drop sp500_constituents table

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-27

The S&P 500 screener has been removed — the swing-only filter doesn't
generalize cleanly to the new user-selectable holding-period model. Drop
the universe table; recreate on downgrade to match the 0005 shape.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("sp500_constituents")


def downgrade() -> None:
    op.create_table(
        "sp500_constituents",
        sa.Column("symbol", sa.String(length=16), primary_key=True),
        sa.Column("company_name", sa.String(length=128), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
    )
