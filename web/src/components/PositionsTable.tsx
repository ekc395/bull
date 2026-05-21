// Open paper positions w/ Close button. Polls /positions every 5s.
"use client";

import Link from "next/link";

import { formatUsd } from "@/lib/format";
import { useClosePosition, usePositions } from "@/lib/queries";

export function PositionsTable() {
  const positions = usePositions();
  const close = useClosePosition();

  return (
    <div className="rounded-lg border bg-white">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
          Positions
        </h2>
        <span className="text-[10px] uppercase tracking-wide text-slate-400">
          Paper
        </span>
      </div>

      {positions.isLoading && (
        <p className="p-4 text-sm text-slate-500">Loading…</p>
      )}
      {positions.isError && (
        <p className="p-4 text-sm text-red-600">Failed to load positions.</p>
      )}
      {positions.data && positions.data.length === 0 && (
        <p className="p-4 text-sm text-slate-500">No open positions.</p>
      )}
      {positions.data && positions.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Symbol</th>
              <th className="px-4 py-2 text-right font-medium">Qty</th>
              <th className="px-4 py-2 text-right font-medium">Avg entry</th>
              <th className="px-4 py-2 text-right font-medium">Market value</th>
              <th className="px-4 py-2 text-right font-medium">Unrealized P/L</th>
              <th className="px-4 py-2 text-right font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {positions.data.map((p) => {
              const pnlClass =
                p.unrealized_pl > 0
                  ? "text-emerald-700"
                  : p.unrealized_pl < 0
                    ? "text-rose-700"
                    : "text-slate-700";
              const isClosing =
                close.isPending && close.variables === p.symbol;
              return (
                <tr key={p.symbol}>
                  <td className="px-4 py-2 font-mono font-medium">
                    <Link
                      href={`/ticker/${encodeURIComponent(p.symbol)}`}
                      className="hover:underline"
                    >
                      {p.symbol}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">{p.qty}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {formatUsd(p.avg_entry_price)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {formatUsd(p.market_value)}
                  </td>
                  <td className={`px-4 py-2 text-right font-mono ${pnlClass}`}>
                    {formatUsd(p.unrealized_pl)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => {
                        if (
                          confirm(
                            `Close paper position ${p.symbol} (${p.qty} shares)?`,
                          )
                        ) {
                          close.mutate(p.symbol);
                        }
                      }}
                      disabled={close.isPending}
                      className="rounded border border-slate-300 px-2 py-0.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isClosing ? "Closing…" : "Close"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {close.isError && (
        <p className="border-t px-4 py-2 text-xs text-red-600">
          Close failed:{" "}
          {close.error instanceof Error
            ? close.error.message
            : "unknown error"}
        </p>
      )}
    </div>
  );
}
