"""init

Revision ID: 0001
Revises:
Create Date: 2026-05-15

Creates verdicts, orders, tickers tables. See api/src/bull_api/models.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verdicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("headline", sa.String(length=280), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("key_levels_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("model_used", sa.String(length=64), nullable=False),
        sa.Column(
            "depth",
            sa.String(length=16),
            nullable=False,
            server_default="standard",
        ),
        sa.Column(
            "parent_verdict_id",
            sa.Integer(),
            sa.ForeignKey("verdicts.id"),
            nullable=True,
        ),
        sa.Column(
            "escalation_recommended",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("escalation_reasons_json", sa.JSON(), nullable=False),
        sa.Column("raw_response_json", sa.JSON(), nullable=False),
        sa.Column("facts_bundle_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_verdicts_ticker", "verdicts", ["ticker"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "verdict_id",
            sa.Integer(),
            sa.ForeignKey("verdicts.id"),
            nullable=True,
        ),
        sa.Column("alpaca_order_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("qty", sa.Float(), nullable=True),
        sa.Column("notional", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("filled_avg_price", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_orders_ticker", "orders", ["ticker"])

    op.create_table(
        "tickers",
        sa.Column("symbol", sa.String(length=16), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("last_analyzed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("tickers")
    op.drop_index("ix_orders_ticker", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_verdicts_ticker", table_name="verdicts")
    op.drop_table("verdicts")
