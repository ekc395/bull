"use client";

// TradingView lightweight-charts wrapper: candlesticks + SMA20/50/200 + dashed S/R lines.
// TODO: createChart, addCandlestickSeries, addLineSeries for SMAs + S/R, ResizeObserver.

export interface PriceChartProps {
  ticker: string;
}

export function PriceChart(_props: PriceChartProps) {
  return <div className="h-[500px] w-full rounded border bg-white" />;
}
