// Per-ticker analysis view. Fires /analyze on mount (backend caches by ET trading day),
// then renders the symbol header, tabbed content, and trade execution.
"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { use, useEffect, useMemo, useState } from "react";

import { AnalysisLoading } from "@/components/AnalysisLoading";
import { AnalystGauge } from "@/components/AnalystGauge";
import { ExecuteOrderButton } from "@/components/ExecuteOrderButton";
import { IndicatorTable } from "@/components/IndicatorTable";
import { KeyFactsCard } from "@/components/KeyFactsCard";
import { KeyFactsToday } from "@/components/KeyFactsToday";
import { KeyLevelsMini } from "@/components/KeyLevelsMini";
import { KeyStatsGrid } from "@/components/KeyStatsGrid";
import { NewsList } from "@/components/NewsList";
import { PerformanceRangeBar } from "@/components/PerformanceRangeBar";
import { PriceChart } from "@/components/PriceChart";
import { KeyLevelsPanel, ReportSections } from "@/components/ReportSections";
import { SymbolHeader } from "@/components/SymbolHeader";
import { SymbolTabs } from "@/components/SymbolTabs";
import { TechnicalsGauge } from "@/components/TechnicalsGauge";
import { TimeframeToggle } from "@/components/TimeframeToggle";
import { VerdictBanner } from "@/components/VerdictBanner";
import { usePrices, useAnalyzeQuery, useVerdict } from "@/lib/queries";
import { computeRangePerformance, type PerfRange } from "@/lib/performance";
import { computeTechnicalRating } from "@/lib/technicalRating";
import { coerceTimeframe, useTimeframe } from "@/lib/timeframe";
import type { Timeframe, VerdictResponse } from "@/types/api";

export default function TickerPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol: raw } = use(params);
  const symbol = decodeURIComponent(raw).toUpperCase();

  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const verdictIdParam = searchParams.get("v");
  const verdictId = verdictIdParam ? Number(verdictIdParam) : null;
  const historical = verdictId !== null && Number.isFinite(verdictId);

  const [storedTimeframe, setStoredTimeframe] = useTimeframe();
  const urlTimeframe = searchParams.get("tf");
  const displayedTimeframe = coerceTimeframe(urlTimeframe, storedTimeframe);
  const [selectedTimeframe, setSelectedTimeframe] =
    useState<Timeframe>(displayedTimeframe);

  useEffect(() => {
    setSelectedTimeframe(displayedTimeframe);
  }, [displayedTimeframe]);

  function onChangeTimeframe(next: Timeframe) {
    setSelectedTimeframe(next);
    setStoredTimeframe(next);
  }

  function runNewAnalysis() {
    const next = new URLSearchParams(searchParams.toString());
    next.delete("v");
    next.set("tf", selectedTimeframe);
    router.replace(`${pathname}?${next.toString()}`);
  }

  const pendingChange = !historical && selectedTimeframe !== displayedTimeframe;

  const analyze = useAnalyzeQuery(historical ? null : symbol, displayedTimeframe);
  const historicalVerdict = useVerdict(historical ? verdictId : null);

  const active = historical ? historicalVerdict : analyze;
  const verdict = active.data;

  const headerActions = (
    <>
      {!historical && (
        <TimeframeToggle
          value={selectedTimeframe}
          onChange={onChangeTimeframe}
          compact
        />
      )}
      {(pendingChange || historical) && (
        <button
          type="button"
          onClick={runNewAnalysis}
          className="rounded-md border border-border-strong bg-elevated px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-input"
        >
          Run new analysis
        </button>
      )}
    </>
  );

  return (
    <div className="space-y-6">
      <SymbolHeader ticker={symbol} verdict={verdict} right={headerActions} />

      {active.isLoading && !verdict && (
        historical ? (
          <p className="rounded-md border border-border bg-panel p-4 text-sm text-muted">
            Loading verdict…
          </p>
        ) : (
          <AnalysisLoading ticker={symbol} />
        )
      )}

      {active.isError && (
        <div className="rounded-md border border-bear bg-panel p-4 text-sm text-bear">
          {active.error instanceof Error
            ? active.error.message
            : historical
              ? "Failed to load verdict."
              : "Analysis failed."}
          <button
            type="button"
            onClick={() => active.refetch()}
            className="ml-3 rounded border border-bear bg-panel px-2 py-0.5 text-xs font-medium hover:bg-elevated"
          >
            Retry
          </button>
        </div>
      )}

      {verdict && historical && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-panel px-4 py-2 text-sm text-secondary">
          <span>
            <span className="text-muted">Viewing saved verdict from </span>
            {new Date(verdict.created_at).toLocaleString()}.
          </span>
        </div>
      )}

      {verdict && (
        <SymbolTabs
          overview={<OverviewTab symbol={symbol} verdict={verdict} />}
          technicals={<TechnicalsTab symbol={symbol} verdict={verdict} />}
          report={
            <ReportSections
              report={verdict.report}
              keyLevels={verdict.key_levels}
            />
          }
          news={<NewsList ticker={symbol} />}
        />
      )}
    </div>
  );
}

function OverviewTab({
  symbol,
  verdict,
}: {
  symbol: string;
  verdict: VerdictResponse;
}) {
  const prices = usePrices(symbol);
  const bars = prices.data?.bars ?? [];
  const perf = useMemo(() => computeRangePerformance(bars), [bars]);

  // Default to the widest computable window (≈ the full series we load).
  const [range, setRange] = useState<PerfRange>("1Y");
  const selected = perf.find((p) => p.key === range && p.available);
  const lastDate = bars.length ? bars[bars.length - 1].date : null;
  const visibleRange =
    selected?.fromDate && lastDate
      ? { from: selected.fromDate, to: lastDate }
      : null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0 space-y-3">
        <PriceChart ticker={symbol} height={560} visibleRange={visibleRange} />
        <PerformanceRangeBar perf={perf} value={range} onSelect={setRange} />
        <div className="space-y-6 pt-3">
          <KeyFactsToday verdict={verdict} />
          <KeyFactsCard ticker={symbol} />
          <AboutCard verdict={verdict} />
          <KeyStatsGrid ticker={symbol} />
          <ExecuteOrderButton verdict={verdict} />
        </div>
      </div>
      <aside className="space-y-6">
        <VerdictBanner verdict={verdict} />
        <KeyLevelsMini keyLevels={verdict.key_levels} />
        <section className="rounded-md border border-border bg-panel">
          <h3 className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
            Top news
          </h3>
          <NewsList ticker={symbol} limit={3} compact />
        </section>
      </aside>
    </div>
  );
}

function TechnicalsTab({
  symbol,
  verdict,
}: {
  symbol: string;
  verdict: VerdictResponse;
}) {
  const prices = usePrices(symbol);
  const rating =
    prices.data != null
      ? computeTechnicalRating(prices.data.indicators, prices.data.current_price)
      : null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0 space-y-6">
        <IndicatorTable ticker={symbol} />
      </div>
      <aside className="space-y-6">
        {rating && <TechnicalsGauge rating={rating} />}
        <AnalystGauge ticker={symbol} />
        <KeyLevelsPanel keyLevels={verdict.key_levels} />
      </aside>
    </div>
  );
}

function AboutCard({ verdict }: { verdict: VerdictResponse }) {
  const [expanded, setExpanded] = useState(false);
  const reasoning = verdict.report.reasoning ?? "";
  const collapsedLen = 360;
  const isLong = reasoning.length > collapsedLen;
  const shown =
    expanded || !isLong ? reasoning : reasoning.slice(0, collapsedLen) + "…";

  return (
    <section className="rounded-md border border-border bg-panel p-5">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
        About
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-secondary">
        {shown}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((s) => !s)}
          className="mt-2 text-xs font-medium text-accent hover:text-accent-hover"
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}
    </section>
  );
}
