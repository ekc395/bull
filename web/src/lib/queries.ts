// TanStack React Query hooks for the FastAPI backend.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiFetch, apiPost } from "./api";
import type {
  AccountResponse,
  AnalyzeRequest,
  ExecuteOrderRequest,
  NewsResponse,
  OrderResponse,
  PortfolioHistoryPeriod,
  PortfolioHistoryResponse,
  PositionResponse,
  PricesResponse,
  ScreenerPreviewResponse,
  ScreenerRunRequest,
  ScreenerRunResponse,
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
  news: (ticker: string) => ["news", ticker.toUpperCase()] as const,
  analyze: (ticker: string) => ["analyze", ticker.toUpperCase()] as const,
  portfolioHistory: (period: PortfolioHistoryPeriod) =>
    ["portfolio-history", period] as const,
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
    queryKey: [...qk.verdicts, limit] as const,
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
export function useAnalyzeQuery(ticker: string | null | undefined) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ticker ? qk.analyze(ticker) : ["analyze", "_none"],
    queryFn: async () => {
      const verdict = await apiPost<VerdictResponse>("/analyze", { ticker });
      qc.setQueryData(qk.verdict(verdict.id), verdict);
      qc.invalidateQueries({ queryKey: qk.verdicts });
      return verdict;
    },
    enabled: !!ticker,
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

export function useScreenerPreview() {
  return useMutation({
    mutationFn: () => apiPost<ScreenerPreviewResponse>("/screener/preview", {}),
  });
}

export function useScreenerRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: ScreenerRunRequest) =>
      apiPost<ScreenerRunResponse>("/screener/run", req),
    onSuccess: (res) => {
      res.verdicts.forEach((v) => qc.setQueryData(qk.verdict(v.id), v));
      qc.invalidateQueries({ queryKey: qk.verdicts });
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
