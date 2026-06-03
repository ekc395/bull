"use client";

// TradingView-style "Seasonals": cumulative year-to-date % for the current year
// and the two prior years, overlaid on a shared Jan→Dec axis (lightweight-charts
// line series). Current year is emphasized (bold blue + end-of-line dot). Each
// year resets to 0% on Jan 1. Data from /seasonals. Descriptive, not a forecast.

import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import { useSeasonals } from "@/lib/queries";

const HEIGHT = 320;

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// Series share a single reference year (see backend), so render the x-axis as
// bare month names instead of the reference year / day-of-month artifacts.
// lightweight-charts may hand us a BusinessDay object or a UTCTimestamp number.
function monthTick(time: unknown): string {
  if (typeof time === "string") {
    // "YYYY-MM-DD"
    const m = Number(time.slice(5, 7));
    return MONTHS[m - 1] ?? "";
  }
  if (typeof time === "number") {
    return MONTHS[new Date(time * 1000).getUTCMonth()] ?? "";
  }
  if (time && typeof time === "object" && "month" in time) {
    const m = (time as { month: number }).month;
    return MONTHS[m - 1] ?? "";
  }
  return "";
}

// Colors assigned by recency: current year first (bold blue), then prior years.
const YEAR_COLORS = ["#2962ff", "#22c55e", "#f59e0b"];

function colorFor(index: number): string {
  return YEAR_COLORS[index] ?? "#9ca3af";
}

export function SeasonalsCard({ ticker }: { ticker: string }) {
  const { data } = useSeasonals(ticker);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  // Create the chart lazily once data (and therefore the container) exist — the
  // card returns null while loading, so the container isn't in the DOM at mount.
  useEffect(() => {
    if (!containerRef.current || !data || data.years.length === 0) return;

    const chart =
      chartRef.current ??
      createChart(containerRef.current, {
        autoSize: true,
        layout: { background: { color: "#000000" }, textColor: "#d1d4dc" },
        grid: {
          vertLines: { color: "#1f1f1f" },
          horzLines: { color: "#1f1f1f" },
        },
        rightPriceScale: { borderColor: "#1f1f1f" },
        timeScale: {
          borderColor: "#1f1f1f",
          timeVisible: false,
          tickMarkFormatter: monthTick,
        },
        localization: { priceFormatter: (v: number) => `${v.toFixed(2)}%` },
      });
    chartRef.current = chart;

    const series: ISeriesApi<"Line">[] = [];
    let baselineDrawn = false;
    data.years.forEach((yr, i) => {
      const current = yr.is_current;
      // Each series draws a colored "{year} {final %}" label on the right price
      // axis at its last value (lightweight-charts last-value label) — mirrors
      // the per-year boxes in the TradingView reference.
      const s = chart.addLineSeries({
        color: colorFor(i),
        lineWidth: current ? 3 : 1,
        priceLineVisible: false,
        lastValueVisible: true,
        title: String(yr.year),
      });
      s.setData(yr.points.map((p) => ({ time: p.t as Time, value: p.v })));
      if (current && yr.points.length > 0) {
        const last = yr.points[yr.points.length - 1];
        s.setMarkers([
          {
            time: last.t as Time,
            position: "inBar",
            shape: "circle",
            color: colorFor(i),
          },
        ]);
      }
      // One zero baseline (mirrors the white reference line in the image).
      if (!baselineDrawn) {
        s.createPriceLine({
          price: 0,
          color: "#3a3a3a",
          lineWidth: 1,
          lineVisible: true,
          axisLabelVisible: false,
        });
        baselineDrawn = true;
      }
      series.push(s);
    });
    chart.timeScale().fitContent();

    return () => {
      series.forEach((s) => chart.removeSeries(s));
    };
  }, [data]);

  // Dispose the chart on unmount.
  useEffect(() => {
    return () => {
      chartRef.current?.remove();
      chartRef.current = null;
    };
  }, []);

  if (!data || data.years.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-baseline justify-between border-b border-border px-4 py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Seasonals
        </h3>
        <span className="text-[11px] text-muted">
          cumulative % from Jan 1 · {data.years.length}y
        </span>
      </div>

      <div className="p-4">
        <div
          ref={containerRef}
          style={{ height: `${HEIGHT}px` }}
          className="w-full"
        />
      </div>
    </div>
  );
}
