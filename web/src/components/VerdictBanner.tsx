// Condensed verdict card sized for the Overview sidebar.
import { TIMEFRAME_LABELS } from "@/lib/timeframe";
import { cn } from "@/lib/utils";
import type { VerdictResponse } from "@/types/api";

const ACTION_STYLES: Record<
  "BUY" | "HOLD" | "SELL",
  { pill: string; accent: string }
> = {
  BUY: { pill: "bg-bull text-white", accent: "text-bull" },
  SELL: { pill: "bg-bear text-white", accent: "text-bear" },
  HOLD: { pill: "bg-elevated text-primary", accent: "text-secondary" },
};

export function VerdictBanner({ verdict }: { verdict: VerdictResponse }) {
  const style = ACTION_STYLES[verdict.action];
  const createdAt = new Date(verdict.created_at);

  return (
    <section className="rounded-md border border-border bg-panel p-4">
      <div className="flex items-center justify-between gap-3">
        <span
          className={cn(
            "inline-flex h-7 items-center rounded px-2.5 text-xs font-bold tracking-wide",
            style.pill,
          )}
        >
          {verdict.action}
        </span>
        <span className={cn("text-2xl font-semibold tabular-nums", style.accent)}>
          {verdict.confidence}%
        </span>
      </div>

      <h2 className="mt-3 text-sm font-semibold leading-snug text-primary">
        {verdict.headline}
      </h2>

      <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-xs">
        <dt className="text-muted">Holding period</dt>
        <dd className="text-right text-primary">
          {TIMEFRAME_LABELS[verdict.timeframe]}
        </dd>
        <dt className="text-muted">Model</dt>
        <dd className="text-right font-mono text-primary">
          {verdict.model_used}
        </dd>
        <dt className="text-muted">Generated</dt>
        <dd className="text-right text-primary">
          {createdAt.toLocaleString()}
        </dd>
      </dl>
    </section>
  );
}
