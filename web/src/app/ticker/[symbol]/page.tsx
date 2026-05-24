// Per-ticker analysis view. Fires /analyze on mount (backend caches by ET trading day),
// then renders the verdict banner, report sections, and news list.
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { use } from "react";

import { AnalysisLoading } from "@/components/AnalysisLoading";
import { DeeperAnalysisButton } from "@/components/DeeperAnalysisButton";
import { ExecuteOrderButton } from "@/components/ExecuteOrderButton";
import { IndicatorTable } from "@/components/IndicatorTable";
import { NewsList } from "@/components/NewsList";
import { PriceChart } from "@/components/PriceChart";
import { ReportSections } from "@/components/ReportSections";
import { VerdictBanner } from "@/components/VerdictBanner";
import { useAnalyzeQuery, useVerdict } from "@/lib/queries";

export default function TickerPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol: raw } = use(params);
  const symbol = decodeURIComponent(raw).toUpperCase();

  // `?v=<id>` opens a specific historical verdict without re-running analysis.
  const searchParams = useSearchParams();
  const verdictIdParam = searchParams.get("v");
  const verdictId = verdictIdParam ? Number(verdictIdParam) : null;
  const historical = verdictId !== null && Number.isFinite(verdictId);

  const analyze = useAnalyzeQuery(historical ? null : symbol);
  const historicalVerdict = useVerdict(historical ? verdictId : null);

  // useDeepenVerdict writes the upgraded verdict into qk.analyze(symbol), so
  // analyze.data reflects the deeper model/confidence after a successful deepen.
  const active = historical ? historicalVerdict : analyze;
  const verdict = active.data;

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

      {active.isLoading && !verdict && (
        historical ? (
          <p className="rounded-lg border bg-white p-4 text-sm text-slate-500">
            Loading verdict…
          </p>
        ) : (
          <AnalysisLoading ticker={symbol} />
        )
      )}

      {active.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {active.error instanceof Error
            ? active.error.message
            : historical
              ? "Failed to load verdict."
              : "Analysis failed."}
          <button
            type="button"
            onClick={() => active.refetch()}
            className="ml-3 rounded border border-red-300 bg-white px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      )}

      {verdict && (
        <>
          {historical && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
              <span>
                Viewing saved verdict from{" "}
                {new Date(verdict.created_at).toLocaleString()}.
              </span>
              <Link
                href={`/ticker/${symbol}`}
                className="rounded border border-amber-300 bg-white px-2 py-0.5 text-xs font-medium hover:bg-amber-100"
              >
                Run new analysis
              </Link>
            </div>
          )}

          <VerdictBanner verdict={verdict} />

          <ExecuteOrderButton verdict={verdict} />

          <DeeperAnalysisButton verdict={verdict} />

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
