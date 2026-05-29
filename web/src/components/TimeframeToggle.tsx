"use client";

import { cn } from "@/lib/utils";
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
        <span className="text-[11px] uppercase tracking-wide text-muted">
          Holding period
        </span>
      )}
      <div className="inline-flex gap-1 rounded-md bg-elevated p-0.5">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            type="button"
            onClick={() => onChange(tf)}
            title={TIMEFRAME_HINTS[tf]}
            aria-pressed={tf === value}
            className={cn(
              "rounded px-3 py-1 text-xs font-semibold transition-colors",
              tf === value
                ? "bg-input text-primary"
                : "text-muted hover:text-primary",
            )}
          >
            {TIMEFRAME_LABELS[tf]}
          </button>
        ))}
      </div>
    </div>
  );
}
