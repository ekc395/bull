"use client";

// TradingView-style performance strip: a segmented row of windows (1D / 5D / 1M / …),
// each showing its % change in bull/bear color. Selecting a segment zooms the chart to
// that window. Renders nothing until we have at least one computable range.

import { cn } from "@/lib/utils";
import type { PerfRange, RangePerf } from "@/lib/performance";

export function PerformanceRangeBar({
  perf,
  value,
  onSelect,
}: {
  perf: RangePerf[];
  value: PerfRange;
  onSelect: (range: PerfRange) => void;
}) {
  if (!perf.some((p) => p.available)) return null;

  return (
    <div className="flex overflow-x-auto rounded-md border border-border bg-panel">
      {perf.map((p) => {
        const selected = p.key === value;
        const up = (p.changePct ?? 0) >= 0;
        return (
          <button
            key={p.key}
            type="button"
            disabled={!p.available}
            onClick={() => onSelect(p.key)}
            className={cn(
              "flex min-w-[88px] flex-1 flex-col gap-0.5 border-r border-border px-3 py-2 text-left transition-colors last:border-r-0",
              selected ? "bg-elevated" : "hover:bg-elevated/60",
              !p.available && "cursor-not-allowed opacity-40 hover:bg-transparent",
            )}
          >
            <span className="whitespace-nowrap text-[11px] text-muted">
              {p.label}
            </span>
            <span
              className={cn(
                "font-mono text-sm font-semibold tabular-nums",
                p.changePct == null ? "text-muted" : up ? "text-bull" : "text-bear",
              )}
            >
              {p.changePct == null
                ? "—"
                : `${up ? "+" : ""}${p.changePct.toFixed(2)}%`}
            </span>
          </button>
        );
      })}
    </div>
  );
}
