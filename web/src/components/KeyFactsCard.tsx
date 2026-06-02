"use client";

// TradingView-style "Key facts" card: company fundamentals (market cap, P/E,
// margins, analyst rating, next earnings) from GET /fundamentals/{ticker}.
// Renders only the facts that have data, so unknown tickers degrade gracefully.

import { cn } from "@/lib/utils";
import { useFundamentals } from "@/lib/queries";
import { formatCompact, formatPct, formatUsd } from "@/lib/format";
import type { FundamentalsResponse } from "@/types/api";

type Tone = "bull" | "bear" | "neutral";

interface Fact {
  label: string;
  value: string;
  tone: Tone;
}

export function KeyFactsCard({ ticker }: { ticker: string }) {
  const { data, isLoading, isError } = useFundamentals(ticker);

  if (isLoading) {
    return (
      <div className="rounded-md border border-border bg-panel p-4 text-sm text-muted">
        Loading key facts…
      </div>
    );
  }
  // Unknown ticker / source outage: stay quiet rather than show an error block.
  if (isError || !data) return null;

  const facts = buildFacts(data);
  if (facts.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Key facts
        </h3>
        {data.source && (
          <span className="text-[10px] text-muted">via {data.source}</span>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3">
        {facts.map((f) => (
          <div
            key={f.label}
            className="bg-panel p-4 transition-colors hover:bg-elevated"
          >
            <dt className="text-[11px] uppercase tracking-wide text-muted">
              {f.label}
            </dt>
            <dd
              className={cn(
                "mt-1 font-mono text-base font-medium",
                toneClass(f.tone),
              )}
            >
              {f.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function toneClass(t: Tone) {
  if (t === "bull") return "text-bull";
  if (t === "bear") return "text-bear";
  return "text-primary";
}

function buildFacts(d: FundamentalsResponse): Fact[] {
  const facts: Fact[] = [];
  const push = (label: string, value: string | null, tone: Tone = "neutral") => {
    if (value != null) facts.push({ label, value, tone });
  };

  if (d.market_cap != null && d.market_cap > 0) {
    push("Market cap", `$${formatCompact(d.market_cap)}`);
  }
  push("P/E (TTM)", num(d.trailing_pe));
  push("Fwd P/E", num(d.forward_pe));
  push("Profit margin", pct(d.profit_margins), toneSign(d.profit_margins));
  push("Revenue growth", pct(d.revenue_growth), toneSign(d.revenue_growth));

  if (d.recommendation_key) {
    push(
      "Analyst rating",
      ratingLabel(d.recommendation_key),
      ratingTone(d.recommendation_key),
    );
  }
  if (d.analyst_target_mean != null) {
    push("Price target", formatUsd(d.analyst_target_mean));
  }

  const earnings = nextEarnings(d);
  if (earnings) push("Next earnings", earnings);

  return facts;
}

function num(n: number | null | undefined): string | null {
  return n == null ? null : n.toFixed(2);
}

function pct(n: number | null | undefined): string | null {
  return n == null ? null : formatPct(n);
}

function toneSign(n: number | null | undefined): Tone {
  if (n == null) return "neutral";
  return n > 0 ? "bull" : n < 0 ? "bear" : "neutral";
}

function ratingLabel(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function ratingTone(key: string): Tone {
  if (key.includes("buy")) return "bull";
  if (key.includes("sell") || key.includes("underperform")) return "bear";
  return "neutral";
}

function nextEarnings(d: FundamentalsResponse): string | null {
  if (d.earnings_date) {
    const when = new Date(`${d.earnings_date}T00:00:00`);
    const date = when.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    if (d.days_until_earnings != null) {
      const n = d.days_until_earnings;
      const rel = n === 0 ? "today" : n > 0 ? `in ${n}d` : `${-n}d ago`;
      return `${date} (${rel})`;
    }
    return date;
  }
  return null;
}
