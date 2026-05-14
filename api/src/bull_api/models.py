"""SQLAlchemy 2.0 ORM models. See plan.md → Backend section."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    action: Mapped[str] = mapped_column(String(8))  # BUY | HOLD | SELL
    confidence: Mapped[int]
    headline: Mapped[str] = mapped_column(String(280))
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    key_levels_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime]

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
    submitted_at: Mapped[datetime]
    filled_avg_price: Mapped[float | None]
    created_at: Mapped[datetime]

    verdict: Mapped["Verdict | None"] = relationship()


class Ticker(Base):
    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    last_analyzed_at: Mapped[datetime | None]
