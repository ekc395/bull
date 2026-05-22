"""SQLAlchemy 2.0 ORM models. See plan.md → Backend section."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .time import now_utc


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    action: Mapped[str] = mapped_column(String(8))  # BUY | HOLD | SELL
    confidence: Mapped[int]
    headline: Mapped[str] = mapped_column(String(280))
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    key_levels_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    model_used: Mapped[str] = mapped_column(String(64))
    depth: Mapped[str] = mapped_column(String(16), default="standard")  # standard | deeper
    parent_verdict_id: Mapped[int | None] = mapped_column(ForeignKey("verdicts.id"), nullable=True)
    escalation_recommended: Mapped[bool] = mapped_column(default=False)
    escalation_reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_response_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    facts_bundle_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    verdict_id: Mapped[int | None] = mapped_column(ForeignKey("verdicts.id"), nullable=True)
    alpaca_order_id: Mapped[str] = mapped_column(String(64), unique=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[float | None]
    notional: Mapped[float | None]
    status: Mapped[str] = mapped_column(String(32))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    filled_avg_price: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    verdict: Mapped["Verdict | None"] = relationship()


class Ticker(Base):
    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VerdictScore(Base):
    """Realized-return score for a past verdict at a fixed trading-day horizon.

    Populated by the scoring job (`bull_api.scoring`) once enough trading days
    have elapsed since the verdict's `created_at`. One row per (verdict_id,
    horizon_days). `hit` is computed dynamically from `action + realized_return_pct`
    in summaries — keeping the threshold out of the schema lets us tune it later
    without a migration.
    """

    __tablename__ = "verdict_scores"
    __table_args__ = (UniqueConstraint("verdict_id", "horizon_days", name="uq_verdict_horizon"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    verdict_id: Mapped[int] = mapped_column(ForeignKey("verdicts.id"), index=True)
    horizon_days: Mapped[int] = mapped_column(Integer)  # trading days
    entry_close: Mapped[float] = mapped_column(Float)
    exit_close: Mapped[float] = mapped_column(Float)
    realized_return_pct: Mapped[float] = mapped_column(Float)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    verdict: Mapped["Verdict"] = relationship()
