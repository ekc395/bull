"""add sp500_constituents table

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-24

Universe table for the S&P 500 screener. Populated by the first scan via
Wikipedia scrape; refreshed weekly. Symbol stored in Yahoo convention (dots
replaced with dashes, e.g. BRK.B -> BRK-B) so it can feed yfinance directly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sp500_constituents",
        sa.Column("symbol", sa.String(length=16), primary_key=True),
        sa.Column("company_name", sa.String(length=128), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sp500_constituents")
