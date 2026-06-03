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
  notional?: number;
  qty?: number;
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

export interface LatestEarnings {
  report_date?: string | null;
  fiscal_period?: string | null;
  eps_actual?: number | null;
  eps_estimate?: number | null;
  eps_surprise_pct?: number | null;
  revenue_actual?: number | null;
  revenue_estimate?: number | null;
}

// GET /fundamentals/{ticker} — mirrors Fundamentals (TypedDict, total=False) on the
// backend, so every field beyond ticker is optional.
export interface FundamentalsResponse {
  ticker: string;
  name?: string;
  sector?: string;
  industry?: string;
  market_cap?: number;
  trailing_pe?: number | null;
  forward_pe?: number | null;
  profit_margins?: number | null;
  revenue_growth?: number | null;
  earnings_date?: string | null;
  days_until_earnings?: number | null;
  analyst_target_mean?: number | null;
  analyst_target_high?: number | null;
  analyst_target_low?: number | null;
  analyst_count?: number | null;
  recommendation_mean?: number | null;
  recommendation_key?: string | null;
  beta?: number | null;
  eps_ttm?: number | null;
  dividend_yield?: number | null; // already in percent units (0.47 → 0.47%)
  shares_float?: number | null;
  shares_outstanding?: number | null;
  net_income?: number | null;
  total_revenue?: number | null;
  fifty_two_week_high?: number | null;
  fifty_two_week_low?: number | null;
  description?: string | null;
  website?: string | null;
  ceo?: string | null;
  headquarters?: string | null;
  employees?: number | null;
  ipo_date?: string | null;
  latest_earnings?: LatestEarnings | null;
  source?: string;
}

// GET /financials/{ticker} — multi-year income-statement series for the charts.
export interface FinancialPeriod {
  period: string; // "FY2026" (annual) or "Apr '26" (quarterly)
  revenue: number | null;
  net_income: number | null;
  ebitda: number | null;
}

export interface FinancialsResponse {
  ticker: string;
  annual: FinancialPeriod[];
  quarterly: FinancialPeriod[];
}

// GET /seasonals/{ticker} — cumulative YTD % per year, overlaid on a Jan→Dec axis.
export interface SeasonalPoint {
  t: string; // "2000-MM-DD" reference-year date (shared Jan→Dec axis)
  v: number; // cumulative % from Jan 1 of that real year
}

export interface SeasonalYear {
  year: number; // real calendar year, e.g. 2026
  is_current: boolean;
  final_pct: number; // last point's cumulative %
  points: SeasonalPoint[];
}

export interface SeasonalsResponse {
  ticker: string;
  years: SeasonalYear[];
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

