// Per-range price performance, computed client-side from the daily OHLCV bars
// (the backend only returns the latest indicator values, not a precomputed series).
// Powers the TradingView-style range strip under the chart: each segment shows the
// % change over a window and, when selected, drives the chart's visible range.

import type { PriceBar } from "@/types/api";

export type PerfRange = "1D" | "5D" | "1M" | "6M" | "YTD" | "1Y";

export interface RangePerf {
  key: PerfRange;
  label: string;
  changePct: number | null;
  fromDate: string | null; // visible-range start for the chart (a real bar date)
  available: boolean;
}

// Trading-day lookbacks (~21/mo, ~252/yr). "ytd" resolves against the calendar year.
const RANGE_DEFS: {
  key: PerfRange;
  label: string;
  lookback: number | "ytd";
  clamp?: boolean; // fall back to the oldest bar when history is short
}[] = [
  { key: "1D", label: "1 day", lookback: 1 },
  { key: "5D", label: "5 days", lookback: 5 },
  { key: "1M", label: "1 month", lookback: 21 },
  { key: "6M", label: "6 months", lookback: 126 },
  { key: "YTD", label: "Year to date", lookback: "ytd", clamp: true },
  { key: "1Y", label: "1 year", lookback: 252, clamp: true },
];

const unavailable = (d: { key: PerfRange; label: string }): RangePerf => ({
  key: d.key,
  label: d.label,
  changePct: null,
  fromDate: null,
  available: false,
});

export function computeRangePerformance(bars: PriceBar[]): RangePerf[] {
  const n = bars.length;
  if (n < 2) return RANGE_DEFS.map(unavailable);

  const last = bars[n - 1];
  const currentYear = new Date(`${last.date}T00:00:00`).getFullYear();

  return RANGE_DEFS.map((d) => {
    let startIdx: number;

    if (d.lookback === "ytd") {
      const firstOfYear = bars.findIndex(
        (b) => new Date(`${b.date}T00:00:00`).getFullYear() === currentYear,
      );
      // Baseline = last close of the prior year when we have it, else first bar.
      startIdx = firstOfYear > 0 ? firstOfYear - 1 : 0;
    } else {
      startIdx = n - 1 - d.lookback;
    }

    if (startIdx < 0) {
      if (!d.clamp) return unavailable(d);
      startIdx = 0;
    }
    if (startIdx >= n - 1) return unavailable(d);

    const start = bars[startIdx];
    if (start.close === 0) return unavailable(d);

    return {
      key: d.key,
      label: d.label,
      changePct: ((last.close - start.close) / start.close) * 100,
      fromDate: start.date,
      available: true,
    };
  });
}
