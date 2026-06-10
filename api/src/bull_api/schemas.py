"""Pydantic request/response schemas. Mirrors `web/src/types/api.ts`."""

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PlainSerializer, model_validator

Action = Literal["BUY", "HOLD", "SELL"]

# Holding-period the user selects in the UI. Drives the prompt variant and the
# tool windows (price-tail bars, news-lookback days) in `agent.py`.
Timeframe = Literal["short", "medium", "long"]


def _utc_iso(v: datetime) -> str:
    # SQLite drops tz info on read, so DateTime(timezone=True) columns come back
    # as naive datetimes that still represent UTC. Tag them so the frontend's
    # new Date(...) doesn't reinterpret a UTC instant as local time.
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.isoformat()


UTCDateTime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str)]


class Level(BaseModel):
    """Accepts both the deterministic S/R shape (touch_count + last_touch_date)
    and the LLM-annotated shape from key_levels (note). All fields except
    price are optional so a single schema covers both sources."""

    price: float
    touch_count: int | None = None
    last_touch_date: str | None = None
    note: str | None = None


class KeyLevels(BaseModel):
    support: list[Level]
    resistance: list[Level]


class Report(BaseModel):
    technical: str
    fundamentals_and_supply_chain: str
    news_sentiment: str
    risks: str
    reasoning: str


class PolicyDecisionResponse(BaseModel):
    """Advisory gating/sizing decision from the learning layer (Phase 3).

    Attached to a verdict for the UI. `act=False` means the policy advises
    against acting (rationale explains why); `size_pct` is the suggested
    position size as a % of equity when acting (0.0 otherwise)."""

    act: bool
    size_pct: float
    rationale: str
    policy_version: str


class StrategyCheck(BaseModel):
    """One filter/setup line item from a strategy's checklist."""

    passed: bool
    value: Any = None
    threshold: Any = None


class StrategyEvaluation(BaseModel):
    """A deterministic strategy's full evaluation of one facts bundle."""

    strategy: str
    candidate_action: Literal["BUY", "HOLD"]
    base_confidence: int
    reason: str
    filters: dict[str, StrategyCheck]
    setup: dict[str, StrategyCheck]
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    reward_risk: float | None = None
    max_hold_trading_days: int


class LlmReview(BaseModel):
    """What the LLM did with the active candidate (veto/shade/coercions)."""

    veto: bool
    veto_reason: str | None = None
    raw_llm_action: str
    raw_llm_confidence: int
    coercions: list[str] = []


class AlgoEvaluation(BaseModel):
    """Short-mode algorithm-first record: every strategy's evaluation, which
    one was active, and the LLM review. Mirrors Verdict.algo_json."""

    active_strategy: str
    evaluations: dict[str, StrategyEvaluation]
    llm_review: LlmReview | None = None


class VerdictResponse(BaseModel):
    id: int
    ticker: str
    action: Action
    confidence: int = Field(ge=0, le=100)
    headline: str
    report: Report
    key_levels: KeyLevels
    created_at: UTCDateTime
    model_used: str
    timeframe: Timeframe = "medium"
    policy: PolicyDecisionResponse | None = None
    # Populated only for short-mode verdicts from the strategy layer onward.
    algo: AlgoEvaluation | None = None


class AnalyzeRequest(BaseModel):
    ticker: str
    force: bool = False
    timeframe: Timeframe = "medium"


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


class PortfolioHistoryResponse(BaseModel):
    timestamp: list[int]
    equity: list[float]
    profit_loss: list[float]
    profit_loss_pct: list[float | None]
    base_value: float | None
    timeframe: str


class OrderResponse(BaseModel):
    id: int
    alpaca_order_id: str
    ticker: str
    side: Literal["buy", "sell"]
    qty: float | None
    notional: float | None
    status: str
    submitted_at: UTCDateTime
    filled_avg_price: float | None


class ExecuteOrderRequest(BaseModel):
    verdict_id: int
    notional: float | None = Field(default=None, gt=0)
    qty: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _exclusive_amount(self) -> "ExecuteOrderRequest":
        if self.notional is not None and self.qty is not None:
            raise ValueError("Provide either notional or qty, not both")
        return self


class WatchlistItemResponse(BaseModel):
    """One watchlist ticker + a summary of its latest short-mode verdict."""

    ticker: str
    verdict_id: int | None = None
    action: Action | None = None
    confidence: int | None = None
    candidate_action: str | None = None
    active_strategy: str | None = None
    created_at: UTCDateTime | None = None
    fresh_today: bool = False  # analyzed this trading day → a batch run is free


class WatchlistResponse(BaseModel):
    active_strategy: str
    items: list[WatchlistItemResponse]


class WatchlistAnalyzeItem(BaseModel):
    ticker: str
    cached: bool | None = None  # None when the analysis errored
    verdict_id: int | None = None
    action: Action | None = None
    confidence: int | None = None
    candidate_action: str | None = None
    error: str | None = None


class WatchlistAnalyzeResponse(BaseModel):
    results: list[WatchlistAnalyzeItem]
    llm_calls_made: int  # the paid-call count — spend stays visible


