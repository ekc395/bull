"use client";

// TradingView lightweight-charts wrapper: candlesticks + SMA 20/50/200 + dashed S/R lines.
// SMAs are computed client-side from the OHLCV bars because the backend only returns the
// most recent indicator value, not a series.

import {
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import { usePrices } from "@/lib/queries";
import type { PriceBar } from "@/types/api";

export interface PriceChartProps {
  ticker: string;
}

const SMA_OVERLAYS = [
  { period: 20, color: "#f97316", title: "SMA 20" },
  { period: 50, color: "#2563eb", title: "SMA 50" },
  { period: 200, color: "#7c3aed", title: "SMA 200" },
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

export function PriceChart({ ticker }: PriceChartProps) {
  const prices = usePrices(ticker);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const smaRefs = useRef<ISeriesApi<"Line">[]>([]);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  // Create chart once.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: "#ffffff" }, textColor: "#334155" },
      grid: {
        vertLines: { color: "#f1f5f9" },
        horzLines: { color: "#f1f5f9" },
      },
      rightPriceScale: { borderColor: "#e2e8f0" },
      timeScale: { borderColor: "#e2e8f0", timeVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });
    chartRef.current = chart;
    candleRef.current = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
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

  // Push data + S/R lines whenever the prices payload changes.
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

    SMA_OVERLAYS.forEach((s, i) => {
      smaRefs.current[i]?.setData(rollingSma(bars, s.period));
    });

    priceLinesRef.current.forEach((pl) => candle.removePriceLine(pl));
    priceLinesRef.current = [];
    for (const lvl of prices.data.support_resistance.support) {
      priceLinesRef.current.push(
        candle.createPriceLine({
          price: lvl.price,
          color: "#10b981",
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
          color: "#ef4444",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `R ${lvl.price.toFixed(2)}`,
        }),
      );
    }

    chart.timeScale().fitContent();
  }, [prices.data]);

  return (
    <div className="relative">
      <div ref={containerRef} className="h-[500px] w-full rounded border bg-white" />
      {prices.isLoading && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">
          Loading chart…
        </div>
      )}
      {prices.isError && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-red-600">
          Failed to load price history.
        </div>
      )}
    </div>
  );
}
