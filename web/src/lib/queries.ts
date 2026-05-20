// TanStack React Query hooks for the FastAPI backend.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiFetch, apiPost } from "./api";
import type {
  AccountResponse,
  AnalyzeRequest,
  ExecuteOrderRequest,
  OrderResponse,
  PositionResponse,
  PricesResponse,
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

export function useAccount() {
  return useQuery({
    queryKey: qk.account,
    queryFn: () => apiFetch<AccountResponse>("/account"),
    refetchInterval: 10_000,
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

export function useDeepenVerdict() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (parentId: number) =>
      apiPost<VerdictResponse>(`/verdicts/${parentId}/deepen`, {}),
    onSuccess: (deeper) => {
      qc.setQueryData(qk.verdict(deeper.id), deeper);
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
