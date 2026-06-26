"use client";

import { cn } from "@/lib/utils";
import { usePrices } from "@/lib/queries";
import type { Indicators } from "@/types/api";

type Tone = "bull" | "bear" | "neutral";

interface Stat {
  label: string;
  value: string;
  hint: string;
  tone: Tone;
}

export function KeyStatsGrid({ ticker }: { ticker: string }) {
  const prices = usePrices(ticker);

  if (prices.isLoading) {
    return (
      <div className="rounded-md border border-border bg-panel p-4 text-sm text-muted">
        Loading key stats…
      </div>
    );
  }
  if (prices.isError || !prices.data) {
    return (
      <div className="rounded-md border border-border bg-panel p-4 text-sm text-bear">
        Failed to load key stats.
      </div>
    );
  }

  const stats = buildStats(prices.data.indicators, prices.data.current_price);

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <h3 className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
        Technical snapshot
      </h3>
      <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3">
        {stats.map((s) => (
          <div
            key={s.label}
            className="bg-panel p-4 transition-colors hover:bg-elevated"
          >
            <dt className="text-[11px] uppercase tracking-wide text-muted">
              {s.label}
            </dt>
            <dd
              className={cn(
                "mt-1 font-mono text-base font-medium",
                toneClass(s.tone),
              )}
            >
              {s.value}
            </dd>
            <dd className="mt-0.5 text-[11px] text-muted">{s.hint}</dd>
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

function buildStats(ind: Indicators, price: number): Stat[] {
  const stats: Stat[] = [];

  stats.push({
    label: "RSI (14)",
    value: fmt(ind.rsi_14, 1),
    hint:
      ind.rsi_14 == null
        ? "n/a"
        : ind.rsi_14 >= 70
          ? "Overbought"
          : ind.rsi_14 <= 30
            ? "Oversold"
            : "Neutral",
    tone:
      ind.rsi_14 == null
        ? "neutral"
        : ind.rsi_14 >= 70
          ? "bear"
          : ind.rsi_14 <= 30
            ? "bull"
            : "neutral",
  });

  stats.push({
    label: "MACD hist",
    value: fmt(ind.macd_hist, 3),
    hint:
      ind.macd_hist == null
        ? "n/a"
        : ind.macd_hist > 0
          ? "Positive momentum"
          : "Negative momentum",
    tone:
      ind.macd_hist == null
        ? "neutral"
        : ind.macd_hist > 0
          ? "bull"
          : "bear",
  });

  stats.push({
    label: "ATR (14)",
    value: fmt(ind.atr_14),
    hint:
      ind.atr_14 == null || price === 0
        ? "n/a"
        : `${((ind.atr_14 / price) * 100).toFixed(2)}% of price`,
    tone: "neutral",
  });

  for (const [label, value] of [
    ["SMA 20", ind.sma_20],
    ["SMA 50", ind.sma_50],
  ] as const) {
    const tone: Tone =
      value == null ? "neutral" : price > value ? "bull" : "bear";
    stats.push({
      label,
      value: fmt(value),
      hint:
        value == null
          ? "n/a"
          : `Price ${price > value ? "above" : "below"} (${pctDelta(price, value)})`,
      tone,
    });
  }

  const volRatio =
    ind.volume_current == null ||
    ind.volume_20d_avg == null ||
    ind.volume_20d_avg === 0
      ? null
      : ind.volume_current / ind.volume_20d_avg;
  stats.push({
    label: "Volume / 20d",
    value: volRatio == null ? "—" : `${volRatio.toFixed(2)}×`,
    hint:
      volRatio == null
        ? "n/a"
        : volRatio >= 1.5
          ? "Above average"
          : volRatio <= 0.5
            ? "Below average"
            : "Normal",
    tone:
      volRatio == null
        ? "neutral"
        : volRatio >= 1.5
          ? "bull"
          : volRatio <= 0.5
            ? "bear"
            : "neutral",
  });

  return stats;
}

function fmt(n: number | null, digits = 2) {
  return n == null ? "—" : n.toFixed(digits);
}

function pctDelta(price: number, ref: number) {
  if (ref === 0) return "n/a";
  const pct = ((price - ref) / ref) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}
