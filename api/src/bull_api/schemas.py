"""Pydantic request/response schemas. Mirrors `web/src/types/api.ts`."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["BUY", "HOLD", "SELL"]


class Level(BaseModel):
    price: float
    touch_count: int
    last_touch_date: str | None = None


class KeyLevels(BaseModel):
    support: list[Level]
    resistance: list[Level]


class Report(BaseModel):
    technical: str
    fundamentals_and_supply_chain: str
    news_sentiment: str
    risks: str
    reasoning: str


class VerdictResponse(BaseModel):
    id: int
    ticker: str
    action: Action
    confidence: int = Field(ge=0, le=100)
    headline: str
    report: Report
    key_levels: KeyLevels
    created_at: datetime
    model_used: str
    depth: Literal["standard", "deeper"]
    parent_verdict_id: int | None
    escalation_recommended: bool
    escalation_reasons: list[str]


class AnalyzeRequest(BaseModel):
    ticker: str
    force: bool = False


class AccountResponse(BaseModel):
    equity: float
    cash: float
    buying_power: float


class PositionResponse(BaseModel):
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float


class OrderResponse(BaseModel):
    id: int
    alpaca_order_id: str
    ticker: str
    side: Literal["buy", "sell"]
    qty: float | None
    notional: float | None
    status: str
    submitted_at: datetime
    filled_avg_price: float | None


class ExecuteOrderRequest(BaseModel):
    verdict_id: int
