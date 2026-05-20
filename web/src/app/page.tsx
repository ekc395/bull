"use client";

import Link from "next/link";

import { AccountPanel } from "@/components/AccountPanel";
import { PositionsTable } from "@/components/PositionsTable";
import { TickerSearch } from "@/components/TickerSearch";
import { TradeJournal } from "@/components/TradeJournal";
import { useVerdicts } from "@/lib/queries";

export default function DashboardPage() {
  const verdicts = useVerdicts(20);

  return (
    <main className="container mx-auto max-w-6xl space-y-8 p-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Bull</h1>
        <p className="text-sm text-slate-600">
          Swing trading agent — analyze a ticker, get a BUY/HOLD/SELL verdict, paper-trade via Alpaca.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">Analyze</h2>
        <TickerSearch />
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <AccountPanel />
        <PositionsTable />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">Recent verdicts</h2>
        <div className="rounded-lg border bg-white">
          {verdicts.isLoading && (
            <p className="p-4 text-sm text-slate-500">Loading…</p>
          )}
          {verdicts.isError && (
            <p className="p-4 text-sm text-red-600">Failed to load verdicts.</p>
          )}
          {verdicts.data && verdicts.data.length === 0 && (
            <p className="p-4 text-sm text-slate-500">
              No verdicts yet — search a ticker above to get started.
            </p>
          )}
          {verdicts.data && verdicts.data.length > 0 && (
            <ul className="divide-y">
              {verdicts.data.map((v) => (
                <li key={v.id}>
                  <Link
                    href={`/ticker/${v.ticker}`}
                    className="flex items-center justify-between gap-4 p-3 text-sm hover:bg-slate-50"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={
                          "inline-block w-14 rounded px-2 py-0.5 text-center text-xs font-semibold " +
                          (v.action === "BUY"
                            ? "bg-emerald-100 text-emerald-800"
                            : v.action === "SELL"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-slate-100 text-slate-700")
                        }
                      >
                        {v.action}
                      </span>
                      <span className="font-mono font-medium">{v.ticker}</span>
                      <span className="text-slate-600">{v.headline}</span>
                    </div>
                    <div className="flex shrink-0 items-center gap-3 text-xs text-slate-500">
                      <span>{v.confidence}%</span>
                      <span className="hidden sm:inline">
                        {new Date(v.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <TradeJournal />

      <footer className="pt-4 text-xs text-slate-400">
        Not financial advice. For research and educational use only.
      </footer>
    </main>
  );
}
