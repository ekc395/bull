// Hand-synced with api/src/bull_api/schemas.py.

export type Action = "BUY" | "HOLD" | "SELL";

export type Timeframe = "short" | "medium" | "long";

export interface Level {
  // Only `price` is required. Backend's Level accepts both deterministic S/R
  // (touch_count, last_touch_date) and LLM-annotated key_levels (note).
  price: number;
  touch_count?: number | null;
  last_touch_date?: string | null;
  note?: string | null;
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
  timeframe: Timeframe;
}

export interface AnalyzeRequest {
  ticker: string;
  force?: boolean;
  timeframe?: Timeframe;
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

export type PortfolioHistoryPeriod = "1D" | "1W" | "1M" | "3M" | "1Y";

export interface PortfolioHistoryResponse {
  timestamp: number[];
  equity: number[];
  profit_loss: number[];
  profit_loss_pct: (number | null)[];
  base_value: number | null;
  timeframe: string;
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

export interface ExecuteOrderRequest {
  verdict_id: number;
}

// Prices endpoint (chart data) — no Pydantic model on the backend; shape lives here.

export interface PriceBar {
  date: string; // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Indicators {
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  sma_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
  ema_12: number | null;
  ema_26: number | null;
  atr_14: number | null;
  volume_20d_avg: number | null;
  volume_current: number | null;
}

export interface SupportResistance {
  support: Level[];
  resistance: Level[];
}

export interface PricesResponse {
  ticker: string;
  current_price: number;
  bars: PriceBar[];
  indicators: Indicators;
  support_resistance: SupportResistance;
}

export interface NewsItem {
  title: string;
  source: string;
  url: string;
  published_at: string;
  summary: string;
}

export interface NewsResponse {
  ticker: string;
  items: NewsItem[];
}

