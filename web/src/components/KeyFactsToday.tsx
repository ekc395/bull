// "Key facts today" — Bull's analogue to TradingView's AI daily summary.
// Surfaces the verdict's one-line headline as the day's takeaway, tagged with
// the BUY/HOLD/SELL action. Not financial advice.
import { cn } from "@/lib/utils";
import type { VerdictResponse } from "@/types/api";

const ACTION_PILL: Record<"BUY" | "HOLD" | "SELL", string> = {
  BUY: "bg-bull text-white",
  SELL: "bg-bear text-white",
  HOLD: "bg-elevated text-primary",
};

export function KeyFactsToday({ verdict }: { verdict: VerdictResponse }) {
  return (
    <section className="rounded-md border border-border bg-panel p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Key facts today
        </h3>
        <span
          className={cn(
            "shrink-0 rounded px-2 py-0.5 text-[11px] font-bold tracking-wide",
            ACTION_PILL[verdict.action],
          )}
        >
          {verdict.action} · {verdict.confidence}%
        </span>
      </div>
      <p className="mt-2 text-base font-semibold leading-snug text-primary">
        {verdict.headline}
      </p>
    </section>
  );
}
