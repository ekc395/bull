"use client";

// TradingView-style "Financials" card: grouped Revenue + Net income bars over
// the last several periods, with an Annual / Quarterly toggle. Data from
// /financials (yfinance income statement). Bars are CSS-scaled to the period max.

import { useState } from "react";

import { cn } from "@/lib/utils";
import { useFinancials } from "@/lib/queries";
import { formatCompact } from "@/lib/format";
import type { FinancialPeriod } from "@/types/api";

type Mode = "annual" | "quarterly";

const CHART_H = 150; // px

export function FinancialsCard({ ticker }: { ticker: string }) {
  const { data } = useFinancials(ticker);
  const [mode, setMode] = useState<Mode>("annual");

  if (!data) return null;
  const periods = mode === "annual" ? data.annual : data.quarterly;
  // Fall back to whichever series has data (e.g. ETFs may lack annual splits).
  const series =
    periods.length > 0
      ? periods
      : mode === "annual"
        ? data.quarterly
        : data.annual;
  if (series.length === 0) return null;

  const max = Math.max(
    1,
    ...series.flatMap((p) => [
      Math.abs(p.revenue ?? 0),
      Math.abs(p.net_income ?? 0),
    ]),
  );

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Financials
        </h3>
        <div className="flex gap-1">
          {(["annual", "quarterly"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn(
                "rounded px-2 py-0.5 text-[11px] font-medium capitalize transition-colors",
                mode === m
                  ? "bg-elevated text-primary"
                  : "text-muted hover:text-secondary",
              )}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4">
        <div className="mb-3 flex items-center gap-4 text-[11px] text-muted">
          <Legend className="bg-accent" label="Revenue" />
          <Legend className="bg-bull" label="Net income" />
        </div>

        <div className="flex items-stretch gap-2" style={{ height: CHART_H }}>
          {series.map((p) => (
            <Column key={p.period} period={p} max={max} />
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          {series.map((p) => (
            <div
              key={p.period}
              className="flex-1 truncate text-center text-[10px] text-muted"
            >
              {p.period}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Column({ period, max }: { period: FinancialPeriod; max: number }) {
  return (
    <div className="flex flex-1 items-end justify-center gap-1">
      <Bar value={period.revenue} max={max} label="Revenue" tone="accent" />
      <Bar
        value={period.net_income}
        max={max}
        label="Net income"
        tone={period.net_income != null && period.net_income < 0 ? "bear" : "bull"}
      />
    </div>
  );
}

function Bar({
  value,
  max,
  label,
  tone,
}: {
  value: number | null;
  max: number;
  label: string;
  tone: "accent" | "bull" | "bear";
}) {
  const pct = value == null ? 0 : (Math.abs(value) / max) * 100;
  const bg =
    tone === "accent" ? "bg-accent" : tone === "bear" ? "bg-bear" : "bg-bull";
  return (
    <div
      className="group relative flex w-1/2 items-end justify-center"
      style={{ height: "100%" }}
      title={`${label}: ${value == null ? "—" : `$${formatCompact(value)}`}`}
    >
      <div
        className={cn("w-full rounded-t", bg)}
        style={{ height: `${Math.max(pct, value == null ? 0 : 2)}%` }}
      />
      {value != null && (
        <span className="absolute -top-4 text-[9px] tabular-nums text-secondary opacity-0 transition-opacity group-hover:opacity-100">
          ${formatCompact(value)}
        </span>
      )}
    </div>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn("inline-block h-2 w-2 rounded-sm", className)} />
      {label}
    </span>
  );
}
