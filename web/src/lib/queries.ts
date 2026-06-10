// TanStack React Query hooks for the FastAPI backend.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiFetch, apiPost } from "./api";
import type {
  AccountResponse,
  AnalyzeRequest,
  ExecuteOrderRequest,
  FinancialsResponse,
  FundamentalsResponse,
  NewsResponse,
  OrderResponse,
  SeasonalsResponse,
  PortfolioHistoryPeriod,
  PortfolioHistoryResponse,
  PositionResponse,
  PricesResponse,
  ScreenResponse,
  Timeframe,
  VerdictResponse,
} from "../types/api";

// ---- Query keys (centralized so invalidations stay consistent) ----

export const qk = {
  account: ["account"] as const,
  positions: ["positions"] as const,
  orders: ["orders"] as const,
  verdicts: ["verdicts"] as const,
  verdict: (id: number) => ["verdicts", id] as const,
  prices: (ticker: string) => ["prices", ticker.toUpperCase()] as const,
  fundamentals: (ticker: string) =>
    ["fundamentals", ticker.toUpperCase()] as const,
  financials: (ticker: string) =>
    ["financials", ticker.toUpperCase()] as const,
  seasonals: (ticker: string) =>
    ["seasonals", ticker.toUpperCase()] as const,
  news: (ticker: string) => ["news", ticker.toUpperCase()] as const,
  analyze: (ticker: string, timeframe: Timeframe) =>
    ["analyze", ticker.toUpperCase(), timeframe] as const,
  portfolioHistory: (period: PortfolioHistoryPeriod) =>
    ["portfolio-history", period] as const,
  screen: ["screen"] as const,
};

// ---- Polling reads ----

export function usePrices(ticker: string | null | undefined, bars = 252) {
  return useQuery({
    queryKey: ticker ? [...qk.prices(ticker), bars] : ["prices", "_none"],
    queryFn: () => apiFetch<PricesResponse>(`/prices/${ticker}?bars=${bars}`),
    enabled: !!ticker,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useFundamentals(ticker: string | null | undefined) {
  return useQuery({
    queryKey: ticker ? qk.fundamentals(ticker) : ["fundamentals", "_none"],
    queryFn: () => apiFetch<FundamentalsResponse>(`/fundamentals/${ticker}`),
    enabled: !!ticker,
    staleTime: 60 * 60_000, // backend caches 24h; an hour is plenty here
    retry: false, // 404 on unknown ticker shouldn't thrash
  });
}

export function useFinancials(ticker: string | null | undefined) {
  return useQuery({
    queryKey: ticker ? qk.financials(ticker) : ["financials", "_none"],
    queryFn: () => apiFetch<FinancialsResponse>(`/financials/${ticker}`),
    enabled: !!ticker,
    staleTime: 60 * 60_000, // backend caches 24h
    retry: false,
  });
}

export function useSeasonals(ticker: string | null | undefined) {
  return useQuery({
    queryKey: ticker ? qk.seasonals(ticker) : ["seasonals", "_none"],
    queryFn: () => apiFetch<SeasonalsResponse>(`/seasonals/${ticker}`),
    enabled: !!ticker,
    staleTime: 60 * 60_000, // backend caches 24h
    retry: false,
  });
}

export function useNews(ticker: string | null | undefined, days = 7) {
  return useQuery({
    queryKey: ticker ? [...qk.news(ticker), days] : ["news", "_none"],
    queryFn: () => apiFetch<NewsResponse>(`/news/${ticker}?days=${days}`),
    enabled: !!ticker,
    staleTime: 5 * 60_000,
  });
}

export function useAccount() {
  return useQuery({
    queryKey: qk.account,
    queryFn: () => apiFetch<AccountResponse>("/account"),
    refetchInterval: 10_000,
  });
}

export function usePortfolioHistory(period: PortfolioHistoryPeriod) {
  return useQuery({
    queryKey: qk.portfolioHistory(period),
    queryFn: () =>
      apiFetch<PortfolioHistoryResponse>(
        `/portfolio/history?period=${encodeURIComponent(period)}`,
      ),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function usePositions() {
  return useQuery({
    queryKey: qk.positions,
    queryFn: () => apiFetch<PositionResponse[]>("/positions"),
    refetchInterval: 5_000,
  });
}

export function useOrders(limit = 50) {
  return useQuery({
    queryKey: [...qk.orders, limit] as const,
    queryFn: () => apiFetch<OrderResponse[]>(`/orders?limit=${limit}`),
    refetchInterval: 15_000,
  });
}

export function useVerdicts(limit = 50) {
  return useQuery({
    // "list" disambiguates from the single-verdict key qk.verdict(id) =
    // ["verdicts", id] — otherwise a limit that equals a verdict id (e.g. both
    // 20) collides and useVerdict reads the cached list array.
    queryKey: [...qk.verdicts, "list", limit] as const,
    queryFn: () => apiFetch<VerdictResponse[]>(`/verdicts?limit=${limit}`),
    refetchInterval: 30_000,
  });
}

export function useVerdict(id: number | null | undefined) {
  return useQuery({
    queryKey: id ? qk.verdict(id) : ["verdicts", "_none"],
    queryFn: () => apiFetch<VerdictResponse>(`/verdicts/${id}`),
    enabled: !!id,
  });
}

// `/analyze` is a POST, but on the ticker page we want it to behave like a query:
// fire once on mount, share state across StrictMode remounts via the React Query cache,
// and stay cached for the rest of the session (backend also caches by ET trading day).
// `timeframe` is part of the key so toggling between short/medium/long doesn't replay
// the same analysis under a different lens — each timeframe gets its own slot.
export function useAnalyzeQuery(
  ticker: string | null | undefined,
  timeframe: Timeframe = "medium",
) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ticker ? qk.analyze(ticker, timeframe) : ["analyze", "_none"],
    queryFn: async () => {
      const verdict = await apiPost<VerdictResponse>("/analyze", { ticker, timeframe });
      qc.setQueryData(qk.verdict(verdict.id), verdict);
      qc.invalidateQueries({ queryKey: qk.verdicts });
      return verdict;
    },
    enabled: !!ticker,
    staleTime: Infinity,
    retry: false,
  });
}

// Free strategy screen over the S&P 500 (no LLM). NEVER auto-fires: the first
// run of a trading day fetches ~500 price histories (minutes); the user
// triggers it via refetch(). Same-day re-runs hit the backend's per-day
// caches and return in seconds. Result kept for the session (staleTime ∞).
export function useScreen() {
  return useQuery({
    queryKey: qk.screen,
    queryFn: () => apiFetch<ScreenResponse>("/screen"),
    enabled: false,
    staleTime: Infinity,
    retry: false,
  });
}

// ---- Mutations ----

export function useAnalyze() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: AnalyzeRequest) => apiPost<VerdictResponse>("/analyze", req),
    onSuccess: (verdict) => {
      qc.setQueryData(qk.verdict(verdict.id), verdict);
      qc.invalidateQueries({ queryKey: qk.verdicts });
    },
  });
}

export function useExecuteOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: ExecuteOrderRequest) => apiPost<OrderResponse>("/orders", req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.positions });
      qc.invalidateQueries({ queryKey: qk.orders });
      qc.invalidateQueries({ queryKey: qk.account });
    },
  });
}

export function useClosePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) =>
      apiDelete<{ alpaca_order_id: string; status: string }>(
        `/positions/${encodeURIComponent(symbol)}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.positions });
      qc.invalidateQueries({ queryKey: qk.orders });
      qc.invalidateQueries({ queryKey: qk.account });
    },
  });
}
