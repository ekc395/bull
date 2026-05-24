// Robinhood-style hero: big equity number, day's change, and an interactive
// equity chart with a 1D/1W/1M/3M/1Y range toggle. Drives off Alpaca's
// /portfolio/history endpoint.
"use client";

import {
  ColorType,
  createChart,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { formatUsd } from "@/lib/format";
import { useAccount, usePortfolioHistory } from "@/lib/queries";
import type { PortfolioHistoryPeriod } from "@/types/api";

const PERIODS: PortfolioHistoryPeriod[] = ["1D", "1W", "1M", "3M", "1Y"];

export function PortfolioHero() {
  const [period, setPeriod] = useState<PortfolioHistoryPeriod>("1D");
  const account = useAccount();
  const history = usePortfolioHistory(period);

  const series = useMemo(() => {
    if (!history.data) return [];
    const { timestamp, equity } = history.data;
    const out: { time: UTCTimestamp; value: number }[] = [];
    for (let i = 0; i < timestamp.length; i++) {
      const v = equity[i];
      // Alpaca returns 0 for time-of-day buckets before the session opens;
      // dropping them keeps the chart from sagging to $0 at the left edge.
      if (v == null || v === 0) continue;
      out.push({ time: timestamp[i] as UTCTimestamp, value: v });
    }
    return out;
  }, [history.data]);

  const { changeUsd, changePct, baseline, current } = useMemo(() => {
    const baselineVal = series.length > 0 ? series[0].value : null;
    const lastSeries = series.length > 0 ? series[series.length - 1].value : null;
    const currentVal = account.data?.equity ?? lastSeries;
    if (baselineVal == null || currentVal == null) {
      return { changeUsd: null, changePct: null, baseline: null, current: currentVal };
    }
    const delta = currentVal - baselineVal;
    const pct = baselineVal === 0 ? null : delta / baselineVal;
    return { changeUsd: delta, changePct: pct, baseline: baselineVal, current: currentVal };
  }, [series, account.data]);

  const isUp = (changeUsd ?? 0) >= 0;
  const accent = isUp ? "#10b981" : "#ef4444";
  const accentArea = isUp ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)";

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Portfolio value
          </p>
          <p className="mt-1 font-mono text-4xl font-semibold tracking-tight text-slate-900">
            {current == null ? "—" : formatUsd(current)}
          </p>
          <p
            className="mt-1 font-mono text-sm"
            style={{ color: changeUsd == null ? "#64748b" : accent }}
          >
            {changeUsd == null ? (
              "—"
            ) : (
              <>
                {isUp ? "+" : ""}
                {formatUsd(changeUsd)}
                {changePct != null && (
                  <span className="ml-2">
                    ({isUp ? "+" : ""}
                    {(changePct * 100).toFixed(2)}%)
                  </span>
                )}
                <span className="ml-2 text-slate-500">{period}</span>
              </>
            )}
          </p>
        </div>

        {account.data && (
          <dl className="grid grid-cols-2 gap-x-6 text-right text-xs">
            <dt className="text-slate-500">Cash</dt>
            <dd className="font-mono text-slate-900">{formatUsd(account.data.cash)}</dd>
            <dt className="text-slate-500">Buying power</dt>
            <dd className="font-mono text-slate-900">
              {formatUsd(account.data.buying_power)}
            </dd>
          </dl>
        )}
      </div>

      <PortfolioChart
        data={series}
        baseline={baseline}
        accent={accent}
        accentArea={accentArea}
        loading={history.isLoading}
        error={history.isError ? "Failed to load portfolio history." : null}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              className={
                "rounded-md px-3 py-1 text-xs font-semibold transition-colors " +
                (p === period
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200")
              }
            >
              {p}
            </button>
          ))}
        </div>
        <span className="text-[10px] uppercase tracking-wide text-slate-400">
          Alpaca paper
        </span>
      </div>
    </section>
  );
}

interface ChartProps {
  data: { time: UTCTimestamp; value: number }[];
  baseline: number | null;
  accent: string;
  accentArea: string;
  loading: boolean;
  error: string | null;
}

function PortfolioChart({ data, baseline, accent, accentArea, loading, error }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#64748b",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "#f1f5f9" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
      handleScroll: false,
      handleScale: false,
    });
    chartRef.current = chart;
    seriesRef.current = chart.addAreaSeries({
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;
    series.applyOptions({
      lineColor: accent,
      topColor: accentArea,
      bottomColor: "rgba(255,255,255,0)",
    });
    series.setData(data);

    // lightweight-charts doesn't expose a list-price-lines API, so we stash the
    // last one on the series object and remove it before re-adding on update.
    const holder = series as unknown as {
      __baselineLine?: ReturnType<typeof series.createPriceLine>;
    };
    if (holder.__baselineLine) {
      try {
        series.removePriceLine(holder.__baselineLine);
      } catch {
        /* already removed */
      }
      holder.__baselineLine = undefined;
    }
    if (baseline != null && data.length > 1) {
      holder.__baselineLine = series.createPriceLine({
        price: baseline,
        color: "#cbd5e1",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
        title: "",
      });
    }

    chart.timeScale().fitContent();
  }, [data, baseline, accent, accentArea]);

  return (
    <div className="relative mt-4">
      <div ref={containerRef} className="h-[220px] w-full" />
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">
          Loading chart…
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-red-600">
          {error}
        </div>
      )}
    </div>
  );
}
