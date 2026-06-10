"""algorithm-first short mode: verdict candidate + order bracket columns

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-09

Short-mode verdicts now carry the deterministic strategy layer's output:
`candidate_action` / `candidate_confidence` (the ACTIVE strategy's decision,
kept as real columns so the scores comparison can grade the algorithm against
the LLM-reviewed final verdict at query time) and `algo_json` (every
registered strategy's evaluation + the LLM review record).

Orders gain bracket-execution fields: `order_class` ("simple" | "bracket"),
`stop_price` / `target_price` (the strategy's exit plan), `legs_json` (Alpaca
leg order ids) and, on sell rows, `exit_reason` ("stop" | "target" |
"time_stop" | "manual").

All columns nullable, no backfill — NULL means "pre-algo row or not a
short-mode strategy trade". batch_alter_table keeps it SQLite-safe and
Postgres-portable (Supabase later).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("verdicts") as batch:
        batch.add_column(sa.Column("candidate_action", sa.String(length=8), nullable=True))
        batch.add_column(sa.Column("candidate_confidence", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("algo_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("order_class", sa.String(length=8), nullable=True))
        batch.add_column(sa.Column("stop_price", sa.Float(), nullable=True))
        batch.add_column(sa.Column("target_price", sa.Float(), nullable=True))
        batch.add_column(sa.Column("legs_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("exit_reason", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("exit_reason")
        batch.drop_column("legs_json")
        batch.drop_column("target_price")
        batch.drop_column("stop_price")
        batch.drop_column("order_class")

    with op.batch_alter_table("verdicts") as batch:
        batch.drop_column("algo_json")
        batch.drop_column("candidate_confidence")
        batch.drop_column("candidate_action")
