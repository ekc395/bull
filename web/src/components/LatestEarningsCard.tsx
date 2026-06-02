"use client";

// TradingView-style "Latest earnings" card: last reported quarter's date,
// fiscal period, EPS (actual vs estimate → beat/miss), and revenue. Data from
// /fundamentals (Finnhub earnings calendar). Renders nothing without a report.

import { cn } from "@/lib/utils";
import { useFundamentals } from "@/lib/queries";
import { formatCompact, formatUsd } from "@/lib/format";
import type { LatestEarnings } from "@/types/api";

export function LatestEarningsCard({ ticker }: { ticker: string }) {
  const { data } = useFundamentals(ticker);
  const e = data?.latest_earnings;
  if (!e || (e.eps_actual == null && e.revenue_actual == null)) return null;

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <h3 className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
        Latest earnings
      </h3>
      <dl className="grid grid-cols-3 gap-px bg-border">
        <Cell label="Fiscal period" value={e.fiscal_period ?? "—"} />
        <Cell
          label="EPS"
          value={e.eps_actual != null ? formatUsd(e.eps_actual) : "—"}
          sub={surpriseText(e.eps_surprise_pct)}
          subTone={surpriseTone(e.eps_surprise_pct)}
        />
        <Cell
          label="Revenue"
          value={
            e.revenue_actual != null ? `$${formatCompact(e.revenue_actual)}` : "—"
          }
        />
      </dl>
    </div>
  );
}

function Cell({
  label,
  value,
  sub,
  subTone = "muted",
}: {
  label: string;
  value: string;
  sub?: string;
  subTone?: "muted" | "bull" | "bear";
}) {
  return (
    <div className="bg-panel p-4">
      <dt className="text-[11px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 font-mono text-base font-medium text-primary">
        {value}
      </dd>
      {sub && (
        <dd
          className={cn(
            "mt-0.5 text-[11px]",
            subTone === "bull"
              ? "text-bull"
              : subTone === "bear"
                ? "text-bear"
                : "text-muted",
          )}
        >
          {sub}
        </dd>
      )}
    </div>
  );
}

function surpriseText(pct: number | null | undefined): string | undefined {
  if (pct == null) return undefined;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}% ${pct >= 0 ? "beat" : "miss"}`;
}

function surpriseTone(pct: number | null | undefined): "muted" | "bull" | "bear" {
  if (pct == null) return "muted";
  return pct >= 0 ? "bull" : "bear";
}
