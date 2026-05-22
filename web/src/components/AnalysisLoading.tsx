// Loading card shown while /analyze is in flight. Spinner + a sub-line that
// cycles through suggestive phase labels every ~4s. Timing is frontend-only
// — the API has no streaming progress channel, so labels mirror the agent's
// phases rather than tracking real events.
"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

const PHASES = [
  "Fetching price history…",
  "Reading recent headlines…",
  "Computing technicals & support/resistance…",
  "Reviewing fundamentals and supply chain…",
  "Synthesizing verdict…",
];

const STEP_MS = 4000;

export function AnalysisLoading({ ticker }: { ticker: string }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (step >= PHASES.length - 1) return;
    const id = setInterval(() => {
      setStep((s) => (s >= PHASES.length - 1 ? s : s + 1));
    }, STEP_MS);
    return () => clearInterval(id);
  }, [step]);

  return (
    <div className="rounded-lg border bg-white p-6">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin text-slate-500" aria-hidden />
        <span>Analyzing {ticker}… this typically takes 15–30 seconds.</span>
      </div>
      <div className="mt-2 pl-6 text-xs text-slate-500">{PHASES[step]}</div>
    </div>
  );
}
