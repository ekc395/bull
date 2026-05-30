"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import { TickerLogo } from "@/components/TickerLogo";
import { useVerdicts } from "@/lib/queries";
import { TIMEFRAME_LABELS } from "@/lib/timeframe";

const ACTION_PILL: Record<
  "BUY" | "HOLD" | "SELL",
  string
> = {
  BUY: "bg-bull text-white",
  SELL: "bg-bear text-white",
  HOLD: "bg-elevated text-primary",
};

export function RecentVerdicts({ limit = 20 }: { limit?: number }) {
  const verdicts = useVerdicts(limit);

  return (
    <section className="rounded-md border border-border bg-panel">
      <h2 className="border-b border-border px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
        Recent verdicts
      </h2>

      {verdicts.isLoading && (
        <p className="p-4 text-sm text-muted">Loading…</p>
      )}
      {verdicts.isError && (
        <p className="p-4 text-sm text-bear">Failed to load verdicts.</p>
      )}
      {verdicts.data && verdicts.data.length === 0 && (
        <p className="p-4 text-sm text-muted">
          No verdicts yet — search a ticker to get started.
        </p>
      )}
      {verdicts.data && verdicts.data.length > 0 && (
        <ul>
          {verdicts.data.map((v) => (
            <li key={v.id} className="border-b border-border last:border-0">
              <Link
                href={`/ticker/${v.ticker}?v=${v.id}`}
                className="block px-4 py-3 transition-colors hover:bg-elevated"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <TickerLogo ticker={v.ticker} size={20} />
                    <span className="font-mono text-sm font-semibold text-primary">
                      {v.ticker}
                    </span>
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide",
                        ACTION_PILL[v.action],
                      )}
                    >
                      {v.action}
                    </span>
                  </div>
                  <span className="shrink-0 text-xs tabular-nums text-secondary">
                    {v.confidence}%
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-secondary">
                  {v.headline}
                </p>
                <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-muted">
                  <span className="uppercase tracking-wide">
                    {TIMEFRAME_LABELS[v.timeframe]}
                  </span>
                  <time>{new Date(v.created_at).toLocaleDateString()}</time>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
