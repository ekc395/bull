// Recent paper orders. Polls /orders every 15s.
"use client";

import { cn } from "@/lib/utils";
import { formatUsd } from "@/lib/format";
import { useOrders } from "@/lib/queries";

export function TradeJournal() {
  const orders = useOrders(50);

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

      {orders.isLoading && (
        <p className="p-4 text-sm text-muted">Loading…</p>
      )}
      {orders.isError && (
        <p className="p-4 text-sm text-bear">Failed to load orders.</p>
      )}
      {orders.data && orders.data.length === 0 && (
        <p className="p-4 text-sm text-muted">
          No paper orders yet — execute a verdict to populate this journal.
        </p>
      )}
      {orders.data && orders.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="border-b border-border text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Submitted</th>
              <th className="px-4 py-2 text-left font-medium">Ticker</th>
              <th className="px-4 py-2 text-left font-medium">Side</th>
              <th className="px-4 py-2 text-right font-medium">Qty</th>
              <th className="px-4 py-2 text-right font-medium">Notional</th>
              <th className="px-4 py-2 text-right font-medium">Fill</th>
              <th className="px-4 py-2 text-left font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.data.map((o) => (
              <tr
                key={o.id}
                className="border-b border-border last:border-0 hover:bg-elevated"
              >
                <td className="px-4 py-2 text-xs text-secondary">
                  {new Date(o.submitted_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 font-mono font-medium text-primary">
                  {o.ticker}
                </td>
                <td className="px-4 py-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase",
                      o.side === "buy"
                        ? "bg-bull/15 text-bull"
                        : "bg-bear/15 text-bear",
                    )}
                  >
                    {o.side}
                  </span>
                </td>
                <td className="px-4 py-2 text-right font-mono text-primary">
                  {o.qty ?? "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono text-primary">
                  {o.notional != null ? formatUsd(o.notional) : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono text-primary">
                  {o.filled_avg_price != null
                    ? formatUsd(o.filled_avg_price)
                    : "—"}
                </td>
                <td className="px-4 py-2 text-xs text-secondary">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
