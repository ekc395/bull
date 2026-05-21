// "Deeper analysis with Opus" opt-in. Surfaces escalation_reasons + cost estimate.
// Never auto-fires — Opus only runs after explicit user confirmation.
"use client";

import { useDeepenVerdict } from "@/lib/queries";
import type { VerdictResponse } from "@/types/api";

const COST_ESTIMATE = "~$0.10–0.15";

export function DeeperAnalysisButton({
  verdict,
  onDeepened,
}: {
  verdict: VerdictResponse;
  onDeepened?: (deeper: VerdictResponse) => void;
}) {
  const deepen = useDeepenVerdict();

  // Don't offer to re-deepen a verdict that's already deeper.
  if (verdict.depth === "deeper") return null;

  const recommended = verdict.escalation_recommended;
  const reasons = verdict.escalation_reasons ?? [];

  const containerClass = recommended
    ? "border-amber-300 bg-amber-50"
    : "border-slate-200 bg-white";

  return (
    <section className={`space-y-3 rounded-lg border p-4 ${containerClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">
            {recommended
              ? "Deeper analysis recommended"
              : "Optional: deeper analysis with Opus"}
          </h3>
          <p className="mt-1 text-xs text-slate-600">
            Opus 4.7 re-analyzes the same facts at higher reasoning depth.
            Costs {COST_ESTIMATE} — billed to your Anthropic API key.
          </p>
        </div>
        <button
          type="button"
          disabled={deepen.isPending}
          onClick={() => {
            const msg =
              `Run deeper Opus analysis on ${verdict.ticker}?\n\n` +
              `Estimated cost: ${COST_ESTIMATE} (Anthropic API).\n\n` +
              `This will reuse the existing facts bundle — no extra data fetches.`;
            if (!confirm(msg)) return;
            deepen.mutate(verdict.id, {
              onSuccess: (deeper) => onDeepened?.(deeper),
            });
          }}
          className="shrink-0 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {deepen.isPending ? "Running Opus…" : "Deepen with Opus"}
        </button>
      </div>

      {recommended && reasons.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-xs text-slate-700">
          {reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}

      {deepen.isError && (
        <p className="text-xs text-red-600">
          {deepen.error instanceof Error
            ? deepen.error.message
            : "Deepen failed."}
        </p>
      )}
    </section>
  );
}
