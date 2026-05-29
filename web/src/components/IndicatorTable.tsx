// RSI, MACD, SMAs, EMAs, ATR, volume with brief interpretations.
"use client";

import { cn } from "@/lib/utils";
import { usePrices } from "@/lib/queries";
import type { Indicators } from "@/types/api";

export function IndicatorTable({ ticker }: { ticker: string }) {
  const prices = usePrices(ticker);

  if (prices.isLoading) {
    return <p className="p-4 text-sm text-muted">Loading indicators…</p>;
  }
  if (prices.isError || !prices.data) {
    return <p className="p-4 text-sm text-bear">Failed to load indicators.</p>;
  }

  const ind = prices.data.indicators;
  const price = prices.data.current_price;
  const rows = buildRows(ind, price);

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <table className="w-full text-sm">
        <thead className="border-b border-border text-[11px] uppercase tracking-wide text-muted">
          <tr>
            <th className="px-4 py-2 text-left font-medium">Indicator</th>
            <th className="px-4 py-2 text-right font-medium">Value</th>
            <th className="px-4 py-2 text-left font-medium">Signal</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-b border-border last:border-0">
              <td className="px-4 py-2 font-medium text-primary">{r.label}</td>
              <td className="px-4 py-2 text-right font-mono text-primary">
                {r.value}
              </td>
              <td className={cn("px-4 py-2 text-xs", toneClass(r.tone))}>
                {r.note}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Tone = "bull" | "bear" | "neutral";

interface Row {
  label: string;
  value: string;
  note: string;
  tone: Tone;
}

function toneClass(t: Tone) {
  if (t === "bull") return "text-bull";
  if (t === "bear") return "text-bear";
  return "text-muted";
}

function fmt(n: number | null, digits = 2) {
  return n == null ? "—" : n.toFixed(digits);
}

function fmtInt(n: number | null) {
  return n == null ? "—" : Math.round(n).toLocaleString();
}

function buildRows(ind: Indicators, price: number): Row[] {
  const rows: Row[] = [];

  rows.push({
    label: "RSI (14)",
    value: fmt(ind.rsi_14, 1),
    note:
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

  const macdSignal =
    ind.macd == null || ind.macd_signal == null
      ? null
      : ind.macd > ind.macd_signal
        ? "bull"
        : "bear";
  rows.push({
    label: "MACD",
    value: `${fmt(ind.macd, 3)} / sig ${fmt(ind.macd_signal, 3)}`,
    note:
      macdSignal == null
        ? "n/a"
        : macdSignal === "bull"
          ? "MACD above signal"
          : "MACD below signal",
    tone: macdSignal ?? "neutral",
  });
  rows.push({
    label: "MACD histogram",
    value: fmt(ind.macd_hist, 3),
    note:
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

  for (const [label, value] of [
    ["SMA 20", ind.sma_20],
    ["SMA 50", ind.sma_50],
    ["SMA 200", ind.sma_200],
  ] as const) {
    const tone: Tone =
      value == null ? "neutral" : price > value ? "bull" : "bear";
    rows.push({
      label,
      value: fmt(value),
      note:
        value == null
          ? "n/a"
          : price > value
            ? `Price above (${pctDelta(price, value)})`
            : `Price below (${pctDelta(price, value)})`,
      tone,
    });
  }

  rows.push({
    label: "EMA 12",
    value: fmt(ind.ema_12),
    note: ind.ema_12 == null ? "n/a" : pctDelta(price, ind.ema_12),
    tone: "neutral",
  });
  rows.push({
    label: "EMA 26",
    value: fmt(ind.ema_26),
    note: ind.ema_26 == null ? "n/a" : pctDelta(price, ind.ema_26),
    tone: "neutral",
  });

  rows.push({
    label: "ATR (14)",
    value: fmt(ind.atr_14),
    note:
      ind.atr_14 == null
        ? "n/a"
        : `${((ind.atr_14 / price) * 100).toFixed(2)}% of price`,
    tone: "neutral",
  });

  const volRatio =
    ind.volume_current == null || ind.volume_20d_avg == null
      ? null
      : ind.volume_current / ind.volume_20d_avg;
  rows.push({
    label: "Volume (today)",
    value: fmtInt(ind.volume_current),
    note: volRatio == null ? "n/a" : `${volRatio.toFixed(2)}× 20-day avg`,
    tone:
      volRatio == null
        ? "neutral"
        : volRatio >= 1.5
          ? "bull"
          : volRatio <= 0.5
            ? "bear"
            : "neutral",
  });
  rows.push({
    label: "Volume (20d avg)",
    value: fmtInt(ind.volume_20d_avg),
    note: "",
    tone: "neutral",
  });

  return rows;
}

function pctDelta(price: number, ref: number) {
  const pct = ((price - ref) / ref) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}
