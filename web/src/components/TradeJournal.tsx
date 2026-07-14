// Round-trip trades (entry buy paired with exit sell) w/ realized P&L. Polls /trades every 15s.
"use client";

import { cn } from "@/lib/utils";
import { formatUsd } from "@/lib/format";
import { useTrades } from "@/lib/queries";

export function TradeJournal() {
  const trades = useTrades(50);

  const closed = (trades.data ?? []).filter((t) => t.pnl != null);
  const realized = closed.reduce((sum, t) => sum + (t.pnl ?? 0), 0);
  const wins = closed.filter((t) => (t.pnl ?? 0) > 0).length;

  return (
    <section className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Trade journal
        </h2>
        <span className="text-[10px] uppercase tracking-wide text-muted">
          Paper
        </span>
      </div>

      {trades.isLoading && (
        <p className="p-4 text-sm text-muted">Loading…</p>
      )}
      {trades.isError && (
        <p className="p-4 text-sm text-bear">Failed to load trades.</p>
      )}
      {trades.data && trades.data.length === 0 && (
        <p className="p-4 text-sm text-muted">
          No paper trades yet — execute a verdict to populate this journal.
        </p>
      )}
      {trades.data && trades.data.length > 0 && (
        <div className="max-h-[480px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 border-b border-border bg-panel text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Opened</th>
              <th className="px-4 py-2 text-left font-medium">Ticker</th>
              <th className="px-4 py-2 text-right font-medium">Qty</th>
              <th className="px-4 py-2 text-right font-medium">Buy</th>
              <th className="px-4 py-2 text-right font-medium">Sell</th>
              <th className="px-4 py-2 text-right font-medium">Net P/L</th>
              <th className="px-4 py-2 text-left font-medium">Exit</th>
            </tr>
          </thead>
          <tbody>
            {trades.data.map((t) => (
              <tr
                key={`${t.status}-${t.sell_order_id ?? t.buy_order_id}`}
                className="border-b border-border last:border-0 hover:bg-elevated"
              >
                <td className="px-4 py-2 text-xs text-secondary">
                  {t.buy_submitted_at != null
                    ? new Date(t.buy_submitted_at).toLocaleString()
                    : "—"}
                </td>
                <td className="px-4 py-2 font-mono font-medium text-primary">
                  {t.ticker}
                </td>
                <td className="px-4 py-2 text-right font-mono text-primary">
                  {t.qty != null ? +t.qty.toFixed(2) : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono text-primary">
                  {t.buy_price != null ? formatUsd(t.buy_price) : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono text-primary">
                  {t.sell_price != null ? formatUsd(t.sell_price) : "—"}
                </td>
                <td
                  className={cn(
                    "px-4 py-2 text-right font-mono",
                    t.pnl != null && t.pnl > 0
                      ? "text-bull"
                      : t.pnl != null && t.pnl < 0
                        ? "text-bear"
                        : "text-secondary",
                  )}
                >
                  {t.pnl != null
                    ? `${formatUsd(t.pnl)}${
                        t.return_pct != null
                          ? ` (${t.return_pct > 0 ? "+" : ""}${t.return_pct.toFixed(2)}%)`
                          : ""
                      }`
                    : "—"}
                </td>
                <td className="px-4 py-2">
                  {t.status === "open" ? (
                    <span className="rounded bg-bull/15 px-1.5 py-0.5 text-[11px] font-semibold uppercase text-bull">
                      open
                    </span>
                  ) : t.exit_reason != null ? (
                    <span className="rounded bg-elevated px-1.5 py-0.5 text-[11px] font-semibold uppercase text-secondary">
                      {t.exit_reason}
                    </span>
                  ) : (
                    <span className="text-xs text-secondary">closed</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}

      {closed.length > 0 && (
        <div className="border-t border-border px-4 py-2 text-xs text-muted">
          Realized{" "}
          <span
            className={cn(
              "font-mono",
              realized > 0
                ? "text-bull"
                : realized < 0
                  ? "text-bear"
                  : "text-secondary",
            )}
          >
            {formatUsd(realized)}
          </span>{" "}
          · {wins}/{closed.length} wins
        </div>
      )}
    </section>
  );
}
