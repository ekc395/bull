"use client";

// TradingView-style "Seasonals": average monthly return across ~N years, drawn
// as up/down bars around a zero baseline (green = positive, red = negative).
// Data from /seasonals. Descriptive statistics, not a forecast.

import { useSeasonals } from "@/lib/queries";
import type { SeasonalMonth } from "@/types/api";

const HALF_H = 70; // px per half (above / below the baseline)

export function SeasonalsCard({ ticker }: { ticker: string }) {
  const { data } = useSeasonals(ticker);
  if (!data || data.months.length === 0) return null;

  const maxAbs = Math.max(
    1e-6,
    ...data.months.map((m) => Math.abs(m.avg_return_pct)),
  );

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-baseline justify-between border-b border-border px-4 py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Seasonals
        </h3>
        <span className="text-[11px] text-muted">
          avg monthly return · {data.years}y
        </span>
      </div>

      <div className="p-4">
        <div className="flex gap-1">
          {data.months.map((m) => (
            <MonthBar key={m.month} m={m} maxAbs={maxAbs} />
          ))}
        </div>
        <div className="mt-2 flex gap-1">
          {data.months.map((m) => (
            <div
              key={m.month}
              className="flex-1 text-center text-[10px] text-muted"
            >
              {m.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MonthBar({ m, maxAbs }: { m: SeasonalMonth; maxAbs: number }) {
  const up = m.avg_return_pct >= 0;
  const pct = Math.max((Math.abs(m.avg_return_pct) / maxAbs) * 100, 3);
  const posYears = Math.round(m.positive_rate * m.sample);
  const sign = up ? "+" : "";
  const title = `${m.label}: ${sign}${m.avg_return_pct.toFixed(1)}% avg · ${posYears}/${m.sample} yrs positive`;

  return (
    <div className="group flex flex-1 flex-col" title={title}>
      <div className="flex items-end justify-center" style={{ height: HALF_H }}>
        {up && (
          <div
            className="w-2/3 rounded-t bg-bull transition-opacity group-hover:opacity-80"
            style={{ height: `${pct}%` }}
          />
        )}
      </div>
      <div className="h-px bg-border-strong" />
      <div className="flex items-start justify-center" style={{ height: HALF_H }}>
        {!up && (
          <div
            className="w-2/3 rounded-b bg-bear transition-opacity group-hover:opacity-80"
            style={{ height: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}
