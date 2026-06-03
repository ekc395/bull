"use client";

// TradingView lightweight-charts wrapper: candlesticks + optional SMA 20/50/200 + dashed S/R lines.
// SMAs are computed client-side from the OHLCV bars because the backend only returns the
// most recent indicator value, not a series. Overlays default to off and are toggled per-chart
// via the chip row above the chart to keep the default view uncluttered.

import {
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import { usePrices } from "@/lib/queries";
import type { PriceBar } from "@/types/api";

export interface PriceChartProps {
  ticker: string;
  height?: number;
  // When set, zooms the time scale to [from, to] (bar dates, YYYY-MM-DD).
  // When null/omitted, the chart fits the full series.
  visibleRange?: { from: string; to: string } | null;
}

type OverlayKey = "sma20" | "sma50" | "sma200" | "levels";

const SMA_OVERLAYS = [
  { key: "sma20", period: 20, color: "#f59e0b", title: "SMA 20" },
  { key: "sma50", period: 50, color: "#60a5fa", title: "SMA 50" },
  { key: "sma200", period: 200, color: "#a78bfa", title: "SMA 200" },
] as const;

// Chips render in this order; "levels" controls both support and resistance lines.
const OVERLAY_TOGGLES: { key: OverlayKey; label: string; color: string }[] = [
  ...SMA_OVERLAYS.map((s) => ({ key: s.key, label: s.title, color: s.color })),
  { key: "levels", label: "Support & Resistance Levels", color: "#26a69a" },
];

function rollingSma(bars: PriceBar[], period: number) {
  if (bars.length < period) return [];
  const out: { time: Time; value: number }[] = [];
  let sum = 0;
  for (let i = 0; i < bars.length; i++) {
    sum += bars[i].close;
    if (i >= period) sum -= bars[i - period].close;
    if (i >= period - 1) {
      out.push({ time: bars[i].date as Time, value: sum / period });
    }
  }
  return out;
}

export function PriceChart({
  ticker,
  height = 560,
  visibleRange = null,
}: PriceChartProps) {
  const prices = usePrices(ticker);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const smaRefs = useRef<ISeriesApi<"Line">[]>([]);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  // Overlay visibility — all off by default so the base chart stays uncluttered.
  const [visible, setVisible] = useState<Record<OverlayKey, boolean>>({
    sma20: false,
    sma50: false,
    sma200: false,
    levels: false,
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: "#000000" }, textColor: "#d1d4dc" },
      grid: {
        vertLines: { color: "#1f1f1f" },
        horzLines: { color: "#1f1f1f" },
      },
      rightPriceScale: { borderColor: "#1f1f1f" },
      timeScale: { borderColor: "#1f1f1f", timeVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });
    chartRef.current = chart;
    candleRef.current = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });
    smaRefs.current = SMA_OVERLAYS.map((s) =>
      chart.addLineSeries({
        color: s.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: s.title,
      }),
    );
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      smaRefs.current = [];
      priceLinesRef.current = [];
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle || !prices.data) return;
    const bars = prices.data.bars;

    candle.setData(
      bars.map((b) => ({
        time: b.date as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );

    // Empty data hides a line series without destroying it, so toggling is cheap.
    SMA_OVERLAYS.forEach((s, i) => {
      smaRefs.current[i]?.setData(visible[s.key] ? rollingSma(bars, s.period) : []);
    });

    priceLinesRef.current.forEach((pl) => candle.removePriceLine(pl));
    priceLinesRef.current = [];
    if (visible.levels) {
      for (const lvl of prices.data.support_resistance.support) {
        priceLinesRef.current.push(
          candle.createPriceLine({
            price: lvl.price,
            color: "#26a69a",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `S ${lvl.price.toFixed(2)}`,
          }),
        );
      }
      for (const lvl of prices.data.support_resistance.resistance) {
        priceLinesRef.current.push(
          candle.createPriceLine({
            price: lvl.price,
            color: "#ef5350",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `R ${lvl.price.toFixed(2)}`,
          }),
        );
      }
    }
  }, [prices.data, visible]);

  // Apply the selected window (or fit the full series). Runs after the data effect
  // above, so the bars are already set when we adjust the visible range.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !prices.data) return;
    const ts = chart.timeScale();
    if (visibleRange && visibleRange.from !== visibleRange.to) {
      try {
        ts.setVisibleRange({
          from: visibleRange.from as Time,
          to: visibleRange.to as Time,
        });
        return;
      } catch {
        // Fall through to fitContent if the range is out of bounds.
      }
    }
    ts.fitContent();
  }, [visibleRange, prices.data]);

  return (
    <div className="relative">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        {OVERLAY_TOGGLES.map(({ key, label, color }) => {
          const on = visible[key];
          return (
            <button
              key={key}
              type="button"
              aria-pressed={on}
              onClick={() =>
                setVisible((prev) => ({ ...prev, [key]: !prev[key] }))
              }
              className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
                on
                  ? "border-border-strong bg-elevated text-primary"
                  : "border-border bg-panel text-muted hover:text-secondary"
              }`}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={
                  on
                    ? { backgroundColor: color }
                    : { boxShadow: `inset 0 0 0 1px ${color}` }
                }
              />
              {label}
            </button>
          );
        })}
      </div>
      <div
        ref={containerRef}
        style={{ height: `${height}px` }}
        className="w-full rounded-md border border-border bg-app"
      />
      {prices.isLoading && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-muted">
          Loading chart…
        </div>
      )}
      {prices.isError && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-bear">
          Failed to load price history.
        </div>
      )}
    </div>
  );
}
