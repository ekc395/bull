// Three-pill segmented control for picking the holding-period timeframe.
// Mirrors the existing PortfolioHero range toggle pattern so the UI stays
// consistent without pulling in a new component dependency.

"use client";

import { TIMEFRAMES, TIMEFRAME_HINTS, TIMEFRAME_LABELS } from "@/lib/timeframe";
import type { Timeframe } from "@/types/api";

interface Props {
  value: Timeframe;
  onChange: (next: Timeframe) => void;
  compact?: boolean;
}

export function TimeframeToggle({ value, onChange, compact = false }: Props) {
  return (
    <div className="flex items-center gap-2">
      {!compact && (
        <span className="text-xs uppercase tracking-wide text-slate-500">
          Holding period
        </span>
      )}
      <div className="inline-flex gap-1 rounded-md bg-slate-100 p-0.5">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            type="button"
            onClick={() => onChange(tf)}
            title={TIMEFRAME_HINTS[tf]}
            aria-pressed={tf === value}
            className={
              "rounded px-3 py-1 text-xs font-semibold transition-colors " +
              (tf === value
                ? "bg-slate-900 text-white shadow-sm"
                : "text-slate-600 hover:text-slate-900")
            }
          >
            {TIMEFRAME_LABELS[tf]}
          </button>
        ))}
      </div>
    </div>
  );
}
