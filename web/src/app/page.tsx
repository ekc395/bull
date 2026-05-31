"use client";

import { PortfolioHero } from "@/components/PortfolioHero";
import { PositionsTable } from "@/components/PositionsTable";
import { RecentVerdicts } from "@/components/RecentVerdicts";
import { TickerSearch } from "@/components/TickerSearch";
import { TimeframeToggle } from "@/components/TimeframeToggle";
import { TradeJournal } from "@/components/TradeJournal";
import { useTimeframe } from "@/lib/timeframe";

export default function DashboardPage() {
  const [timeframe, setTimeframe] = useTimeframe();

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-primary">
          Dashboard
        </h1>
        <p className="text-xs text-muted">
          Trading agent — pick a holding period, get a BUY/HOLD/SELL verdict,
          paper-trade via Alpaca.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <PortfolioHero />
          <PositionsTable />
          <TradeJournal />
        </div>

        <aside className="flex flex-col gap-6">
          <section className="space-y-3 rounded-md border border-border bg-panel p-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                Analyze
              </h2>
              <TimeframeToggle
                value={timeframe}
                onChange={setTimeframe}
                compact
              />
            </div>
            <TickerSearch timeframe={timeframe} />
          </section>

          <RecentVerdicts limit={20} />
        </aside>
      </div>
    </div>
  );
}
