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
  height?: number;
}

const SMA_OVERLAYS = [
  { period: 20, color: "#f59e0b", title: "SMA 20" },
  { period: 50, color: "#60a5fa", title: "SMA 50" },
  { period: 200, color: "#a78bfa", title: "SMA 200" },
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

export function PriceChart({ ticker, height = 560 }: PriceChartProps) {
  const prices = usePrices(ticker);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const smaRefs = useRef<ISeriesApi<"Line">[]>([]);
  const priceLinesRef = useRef<IPriceLine[]>([]);

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

    SMA_OVERLAYS.forEach((s, i) => {
      smaRefs.current[i]?.setData(rollingSma(bars, s.period));
    });

    priceLinesRef.current.forEach((pl) => candle.removePriceLine(pl));
    priceLinesRef.current = [];
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

    chart.timeScale().fitContent();
  }, [prices.data]);

  return (
    <div className="relative">
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
