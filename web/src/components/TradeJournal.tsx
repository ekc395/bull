// Recent paper orders. Polls /orders every 15s.
"use client";

import { formatUsd } from "@/lib/format";
import { useOrders } from "@/lib/queries";

export function TradeJournal() {
  const orders = useOrders(50);

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
        Trade journal
      </h2>
      <div className="rounded-lg border bg-white">
        {orders.isLoading && (
          <p className="p-4 text-sm text-slate-500">Loading…</p>
        )}
        {orders.isError && (
          <p className="p-4 text-sm text-red-600">Failed to load orders.</p>
        )}
        {orders.data && orders.data.length === 0 && (
          <p className="p-4 text-sm text-slate-500">
            No paper orders yet — execute a verdict to populate this journal.
          </p>
        )}
        {orders.data && orders.data.length > 0 && (
          <table className="w-full text-sm">
            <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
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
            <tbody className="divide-y">
              {orders.data.map((o) => (
                <tr key={o.id}>
                  <td className="px-4 py-2 text-xs text-slate-600">
                    {new Date(o.submitted_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 font-mono font-medium">{o.ticker}</td>
                  <td className="px-4 py-2">
                    <span
                      className={
                        "rounded px-1.5 py-0.5 text-xs font-semibold uppercase " +
                        (o.side === "buy"
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-rose-100 text-rose-800")
                      }
                    >
                      {o.side}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {o.qty ?? "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {o.notional != null ? formatUsd(o.notional) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {o.filled_avg_price != null
                      ? formatUsd(o.filled_avg_price)
                      : "—"}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-600">{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
