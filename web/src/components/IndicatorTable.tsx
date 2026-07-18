// RSI, MACD, SMAs, EMAs, ATR, volume grouped into cards with Buy/Sell/Neutral pills.
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

  // Left column (3 + 2 rows) matches the right column (5 rows) so the
  // two columns end at the same height.
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-6">
        <GroupCard title="Oscillators" rows={oscillatorRows(ind)} />
        <GroupCard
          title="Volatility & volume"
          rows={volatilityVolumeRows(ind, price)}
        />
      </div>
      <GroupCard title="Moving averages" rows={movingAverageRows(ind, price)} />
    </div>
  );
}

type Tone = "bull" | "bear" | "neutral";

interface Row {
  label: string;
  value: string;
  note: string;
  // bull/bear/neutral render a Buy/Sell/Neutral pill; null is informational.
  signal: Tone | null;
}

function GroupCard({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <h3 className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {title}
      </h3>
      {rows.map((r) => (
        <div
          key={r.label}
          className="flex items-center gap-3 border-b border-border px-4 py-2 last:border-0"
        >
          <span className="flex-1 truncate text-sm font-medium text-primary">
            {r.label}
          </span>
          {r.note && (
            <span className="hidden text-xs text-muted sm:inline">{r.note}</span>
          )}
          <span className="font-mono text-sm text-primary">{r.value}</span>
          <SignalPill signal={r.signal} />
        </div>
      ))}
    </div>
  );
}

function SignalPill({ signal }: { signal: Tone | null }) {
  if (signal == null) {
    return (
      <span className="inline-flex min-w-[3.75rem] justify-center text-xs text-muted">
        —
      </span>
    );
  }
  const text = signal === "bull" ? "Buy" : signal === "bear" ? "Sell" : "Neutral";
  return (
    <span
      className={cn(
        "inline-flex min-w-[3.75rem] justify-center rounded-full px-2 py-0.5 text-[11px] font-medium",
        signal === "bull" && "bg-bull/10 text-bull",
        signal === "bear" && "bg-bear/10 text-bear",
        signal === "neutral" && "bg-elevated text-secondary",
      )}
    >
      {text}
    </span>
  );
}

function fmt(n: number | null, digits = 2) {
  return n == null ? "—" : n.toFixed(digits);
}

function fmtInt(n: number | null) {
  return n == null ? "—" : Math.round(n).toLocaleString();
}

function oscillatorRows(ind: Indicators): Row[] {
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
            : "",
    signal:
      ind.rsi_14 == null
        ? null
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
        ? ("bull" as const)
        : ("bear" as const);
  rows.push({
    label: "MACD",
    value: fmt(ind.macd, 3),
    note: macdSignal == null ? "n/a" : `vs signal ${fmt(ind.macd_signal, 3)}`,
    signal: macdSignal,
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
    signal: ind.macd_hist == null ? null : ind.macd_hist > 0 ? "bull" : "bear",
  });

  return rows;
}

function movingAverageRows(ind: Indicators, price: number): Row[] {
  const rows: Row[] = [];

  for (const [label, value] of [
    ["SMA 20", ind.sma_20],
    ["SMA 50", ind.sma_50],
    ["SMA 200", ind.sma_200],
  ] as const) {
    rows.push({
      label,
      value: fmt(value),
      note: value == null ? "n/a" : `Price ${pctDelta(price, value)}`,
      signal: value == null ? null : price > value ? "bull" : "bear",
    });
  }

  rows.push({
    label: "EMA 12",
    value: fmt(ind.ema_12),
    note: ind.ema_12 == null ? "n/a" : `Price ${pctDelta(price, ind.ema_12)}`,
    signal: null,
  });
  rows.push({
    label: "EMA 26",
    value: fmt(ind.ema_26),
    note: ind.ema_26 == null ? "n/a" : `Price ${pctDelta(price, ind.ema_26)}`,
    signal: null,
  });

  return rows;
}

function volatilityVolumeRows(ind: Indicators, price: number): Row[] {
  const rows: Row[] = [];

  rows.push({
    label: "ATR (14)",
    value: fmt(ind.atr_14),
    note:
      ind.atr_14 == null || price === 0
        ? "n/a"
        : `${((ind.atr_14 / price) * 100).toFixed(2)}% of price`,
    signal: null,
  });

  const volRatio =
    ind.volume_current == null ||
    ind.volume_20d_avg == null ||
    ind.volume_20d_avg === 0
      ? null
      : ind.volume_current / ind.volume_20d_avg;
  rows.push({
    label: "Volume",
    value: fmtInt(ind.volume_current),
    note: volRatio == null ? "n/a" : `${volRatio.toFixed(2)}× 20-day avg`,
    signal:
      volRatio == null
        ? null
        : volRatio >= 1.5
          ? "bull"
          : volRatio <= 0.5
            ? "bear"
            : null,
  });

  return rows;
}

function pctDelta(price: number, ref: number) {
  if (ref === 0) return "n/a";
  const pct = ((price - ref) / ref) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}
