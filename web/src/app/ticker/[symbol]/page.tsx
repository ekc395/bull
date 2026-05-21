// Per-ticker analysis view. Fires /analyze on mount (backend caches by ET trading day),
// then renders the verdict banner, report sections, and news list.
"use client";

import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";

import { DeeperAnalysisButton } from "@/components/DeeperAnalysisButton";
import { ExecuteOrderButton } from "@/components/ExecuteOrderButton";
import { IndicatorTable } from "@/components/IndicatorTable";
import { NewsList } from "@/components/NewsList";
import { PriceChart } from "@/components/PriceChart";
import { ReportSections } from "@/components/ReportSections";
import { VerdictBanner } from "@/components/VerdictBanner";
import { useAnalyze } from "@/lib/queries";
import type { VerdictResponse } from "@/types/api";

export default function TickerPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol: raw } = use(params);
  const symbol = decodeURIComponent(raw).toUpperCase();

  const analyze = useAnalyze();
  const triggered = useRef<string | null>(null);
  const [deeperVerdict, setDeeperVerdict] = useState<VerdictResponse | null>(null);

  useEffect(() => {
    if (!symbol || triggered.current === symbol) return;
    triggered.current = symbol;
    setDeeperVerdict(null);
    analyze.mutate({ ticker: symbol });
    // analyze.mutate identity is stable across renders; we intentionally key off symbol only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  const verdict = deeperVerdict ?? analyze.data;

  return (
    <main className="container mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="text-sm text-slate-500 hover:text-slate-900"
        >
          ← Dashboard
        </Link>
        <h1 className="font-mono text-2xl font-semibold tracking-tight">
          {symbol}
        </h1>
      </div>

      {analyze.isPending && !verdict && (
        <div className="rounded-lg border bg-white p-6 text-sm text-slate-600">
          Analyzing {symbol}… this typically takes 15–30 seconds.
        </div>
      )}

      {analyze.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {analyze.error instanceof Error
            ? analyze.error.message
            : "Analysis failed."}
          <button
            type="button"
            onClick={() => {
              triggered.current = null;
              analyze.reset();
              triggered.current = symbol;
              analyze.mutate({ ticker: symbol });
            }}
            className="ml-3 rounded border border-red-300 bg-white px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      )}

      {verdict && (
        <>
          <VerdictBanner verdict={verdict} />

          <ExecuteOrderButton verdict={verdict} />

          <DeeperAnalysisButton
            verdict={verdict}
            onDeepened={setDeeperVerdict}
          />

          <section className="space-y-2">
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-500">
              Chart
            </h3>
            <PriceChart ticker={symbol} />
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-500">
              Indicators
            </h3>
            <div className="overflow-hidden rounded-lg border bg-white">
              <IndicatorTable ticker={symbol} />
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-500">
              Report
            </h3>
            <ReportSections
              report={verdict.report}
              keyLevels={verdict.key_levels}
            />
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-500">
              Recent news
            </h3>
            <div className="rounded-lg border bg-white">
              <NewsList ticker={symbol} />
            </div>
          </section>
        </>
      )}

      <footer className="pt-4 text-xs text-slate-400">
        Not financial advice. For research and educational use only.
      </footer>
    </main>
  );
}
