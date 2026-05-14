// Hand-synced with api/src/bull_api/schemas.py.

export type Action = "BUY" | "HOLD" | "SELL";

export interface Level {
  price: number;
  touch_count: number;
  last_touch_date: string | null;
}

export interface KeyLevels {
  support: Level[];
  resistance: Level[];
}

export interface Report {
  technical: string;
  fundamentals_and_supply_chain: string;
  news_sentiment: string;
  risks: string;
  reasoning: string;
}

export interface VerdictResponse {
  id: number;
  ticker: string;
  action: Action;
  confidence: number;
  headline: string;
  report: Report;
  key_levels: KeyLevels;
  created_at: string;
  model_used: string;
  depth: "standard" | "deeper";
  parent_verdict_id: number | null;
  escalation_recommended: boolean;
  escalation_reasons: string[];
}

export interface AccountResponse {
  equity: number;
  cash: number;
  buying_power: number;
}

export interface PositionResponse {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  market_value: number;
  unrealized_pl: number;
}

export interface OrderResponse {
  id: number;
  alpaca_order_id: string;
  ticker: string;
  side: "buy" | "sell";
  qty: number | null;
  notional: number | null;
  status: string;
  submitted_at: string;
  filled_avg_price: number | null;
}
