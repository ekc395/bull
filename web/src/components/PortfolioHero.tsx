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

import { cn } from "@/lib/utils";
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
  const accent = isUp ? "#26a69a" : "#ef5350";
  const accentArea = isUp ? "rgba(38,166,154,0.18)" : "rgba(239,83,80,0.18)";

  return (
    <section className="rounded-md border border-border bg-panel p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Portfolio value
          </p>
          <p className="mt-1 font-mono text-4xl font-semibold tracking-tight text-primary">
            {current == null ? "—" : formatUsd(current)}
          </p>
          <p
            className={cn(
              "mt-1 font-mono text-sm",
              changeUsd == null
                ? "text-muted"
                : isUp
                  ? "text-bull"
                  : "text-bear",
            )}
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
                <span className="ml-2 text-muted">{period}</span>
              </>
            )}
          </p>
        </div>

        {account.data && (
          <dl className="grid grid-cols-2 gap-x-6 text-right text-xs">
            <dt className="text-muted">Cash</dt>
            <dd className="font-mono text-primary">
              {formatUsd(account.data.cash)}
            </dd>
            <dt className="text-muted">Buying power</dt>
            <dd className="font-mono text-primary">
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
        <div className="flex gap-1 rounded-md bg-elevated p-0.5">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              className={cn(
                "rounded px-3 py-1 text-xs font-semibold transition-colors",
                p === period
                  ? "bg-input text-primary"
                  : "text-muted hover:text-primary",
              )}
            >
              {p}
            </button>
          ))}
        </div>
        <span className="text-[10px] uppercase tracking-wide text-muted">
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
        background: { type: ColorType.Solid, color: "#0f0f0f" },
        textColor: "#787b86",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "#1f1f1f" },
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
      bottomColor: "rgba(15,15,15,0)",
    });
    series.setData(data);

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
        color: "#2e2e2e",
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
        <div className="absolute inset-0 flex items-center justify-center text-sm text-muted">
          Loading chart…
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-bear">
          {error}
        </div>
      )}
    </div>
  );
}
