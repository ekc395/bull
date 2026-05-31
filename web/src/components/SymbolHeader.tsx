"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { TickerLogo } from "@/components/TickerLogo";
import { usePrices } from "@/lib/queries";
import { formatUsd } from "@/lib/format";
import type { VerdictResponse } from "@/types/api";

const ACTION_PILL: Record<
  "BUY" | "HOLD" | "SELL",
  string
> = {
  BUY: "bg-bull text-white",
  SELL: "bg-bear text-white",
  HOLD: "bg-elevated text-primary",
};

export function SymbolHeader({
  ticker,
  verdict,
  exchange = "NASDAQ",
  right,
}: {
  ticker: string;
  verdict?: VerdictResponse;
  exchange?: string;
  right?: ReactNode;
}) {
  const prices = usePrices(ticker);
  const bars = prices.data?.bars ?? [];
  const current = prices.data?.current_price ?? null;
  const previous = bars.length >= 2 ? bars[bars.length - 2].close : null;

  const change = current != null && previous != null ? current - previous : null;
  const changePct =
    change != null && previous != null && previous !== 0
      ? (change / previous) * 100
      : null;
  const isUp = (change ?? 0) >= 0;

  return (
    <section className="border-b border-border pb-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <TickerLogo ticker={ticker} size={36} />
            <h1 className="font-mono text-3xl font-bold tracking-tight text-primary">
              {ticker}
            </h1>
            <span className="rounded bg-elevated px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-secondary">
              {exchange}
            </span>
            {verdict && (
              <span
                className={cn(
                  "rounded px-2 py-0.5 text-[11px] font-bold tracking-wide",
                  ACTION_PILL[verdict.action],
                )}
              >
                {verdict.action} · {verdict.confidence}%
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-baseline gap-3">
            <span className="font-mono text-[40px] font-semibold leading-none text-primary">
              {current == null ? "—" : formatUsd(current)}
            </span>
            <span
              className={cn(
                "inline-flex items-baseline font-mono text-base font-medium",
                change == null
                  ? "text-muted"
                  : isUp
                    ? "text-bull"
                    : "text-bear",
              )}
            >
              {change != null && (
                <span aria-hidden className="mr-1 text-xs">
                  {isUp ? "▲" : "▼"}
                </span>
              )}
              {change == null
                ? ""
                : `${isUp ? "+" : ""}${change.toFixed(2)}`}
              {changePct != null && (
                <span className="ml-1.5">
                  ({isUp ? "+" : ""}
                  {changePct.toFixed(2)}%)
                </span>
              )}
            </span>
            <span className="text-[11px] uppercase tracking-wide text-muted">
              {previous == null ? "" : "since previous close"}
            </span>
          </div>
        </div>

        {right && (
          <div className="flex shrink-0 items-center gap-3">{right}</div>
        )}
      </div>
    </section>
  );
}
