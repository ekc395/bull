// Today's setups: the free S&P 500 strategy screen, manually triggered.
// Candidates link to the ticker page where the paid Opus analysis (and the
// bracket execution) happens. First run of a day takes minutes; re-runs are
// cached server-side per trading day.
"use client";

import Link from "next/link";

import { TickerLogo } from "@/components/TickerLogo";
import { useScreen } from "@/lib/queries";

export function ScreenerCard() {
  const screen = useScreen();
  const running = screen.isFetching;
  const report = screen.data;

  return (
    <section className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Today&apos;s setups
        </h2>
        <button
          onClick={() => screen.refetch()}
          disabled={running}
          className="rounded bg-elevated px-2 py-1 text-[11px] font-semibold text-primary transition-colors hover:bg-border disabled:opacity-50"
        >
          {running ? "Scanning…" : report ? "Re-run" : "Run screen"}
        </button>
      </div>

      {!report && !running && !screen.isError && (
        <p className="p-4 text-xs text-muted">
          Scan the S&amp;P 500 with the active strategy — free, no LLM. First
          run of the day takes a couple of minutes.
        </p>
      )}
      {running && (
        <p className="p-4 text-xs text-muted">
          Scanning ~500 names… first run of a trading day fetches fresh price
          history; re-runs are fast.
        </p>
      )}
      {screen.isError && !running && (
        <p className="p-4 text-xs text-bear">
          Screen failed: {(screen.error as Error)?.message ?? "unknown error"}
        </p>
      )}

      {report && !running && (
        <>
          <p className="border-b border-border px-4 py-2 text-[10px] text-muted">
            {report.as_of} · {report.active_strategy} · {report.evaluated} of{" "}
            {report.universe_size} evaluated ·{" "}
            {report.candidates.length === 0
              ? "no setups today (flat is the default)"
              : `${report.candidates.length} candidate(s)`}
          </p>
          {report.candidates.length > 0 && (
            <ul className="max-h-[340px] overflow-y-auto">
              {report.candidates.map((c) => (
                <li key={c.ticker} className="border-b border-border last:border-0">
                  <Link
                    href={`/ticker/${c.ticker}?tf=short`}
                    className="block px-4 py-2.5 transition-colors hover:bg-elevated"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <TickerLogo ticker={c.ticker} size={18} />
                        <span className="font-mono text-sm font-semibold text-primary">
                          {c.ticker}
                        </span>
                        <span className="rounded bg-bull/15 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-bull">
                          SETUP
                        </span>
                      </div>
                      <span className="shrink-0 text-xs tabular-nums text-secondary">
                        {c.base_confidence}%
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-[10px] tabular-nums text-muted">
                      <span>E {c.entry?.toFixed(2) ?? "—"}</span>
                      <span className="text-bear">S {c.stop?.toFixed(2) ?? "—"}</span>
                      <span className="text-bull">T {c.target?.toFixed(2) ?? "—"}</span>
                      <span>R:R {c.reward_risk ?? "—"}</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <p className="px-4 py-2 text-[10px] text-muted">
            Click a setup to run the full analysis (paid Opus call) and execute
            with its bracket. Not financial advice.
          </p>
        </>
      )}
    </section>
  );
}
