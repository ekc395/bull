// Color-coded card: action + confidence + headline + model_used badge.
import type { VerdictResponse } from "@/types/api";

const ACTION_STYLES = {
  BUY: {
    container: "border-emerald-200 bg-emerald-50",
    pill: "bg-emerald-600 text-white",
    accent: "text-emerald-800",
  },
  SELL: {
    container: "border-rose-200 bg-rose-50",
    pill: "bg-rose-600 text-white",
    accent: "text-rose-800",
  },
  HOLD: {
    container: "border-slate-200 bg-slate-50",
    pill: "bg-slate-700 text-white",
    accent: "text-slate-800",
  },
} as const;

export function VerdictBanner({ verdict }: { verdict: VerdictResponse }) {
  const style = ACTION_STYLES[verdict.action];
  const createdAt = new Date(verdict.created_at);

  return (
    <section className={`rounded-lg border p-5 ${style.container}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <span
            className={`inline-flex h-14 w-20 items-center justify-center rounded-md text-xl font-bold tracking-wide ${style.pill}`}
          >
            {verdict.action}
          </span>
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
              <span className="font-mono">{verdict.ticker}</span>
              <span>·</span>
              <span>{createdAt.toLocaleString()}</span>
            </div>
            <h2 className={`text-lg font-semibold leading-snug ${style.accent}`}>
              {verdict.headline}
            </h2>
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          <div className="text-xs uppercase tracking-wide text-slate-500">Confidence</div>
          <div className={`text-2xl font-semibold ${style.accent}`}>
            {verdict.confidence}%
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="rounded bg-white/70 px-2 py-0.5 font-mono">
          {verdict.model_used}
        </span>
        <span className="ml-auto italic">Not financial advice.</span>
      </div>
    </section>
  );
}
