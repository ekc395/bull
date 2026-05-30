// Open paper positions w/ Close button. Polls /positions every 5s.
"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import { TickerLogo } from "@/components/TickerLogo";
import { formatUsd } from "@/lib/format";
import { useClosePosition, usePositions } from "@/lib/queries";

export function PositionsTable() {
  const positions = usePositions();
  const close = useClosePosition();

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Positions
        </h2>
        <span className="text-[10px] uppercase tracking-wide text-muted">
          Paper
        </span>
      </div>

      {positions.isLoading && (
        <p className="p-4 text-sm text-muted">Loading…</p>
      )}
      {positions.isError && (
        <p className="p-4 text-sm text-bear">Failed to load positions.</p>
      )}
      {positions.data && positions.data.length === 0 && (
        <p className="p-4 text-sm text-muted">No open positions.</p>
      )}
      {positions.data && positions.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="border-b border-border text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Symbol</th>
              <th className="px-4 py-2 text-right font-medium">Qty</th>
              <th className="px-4 py-2 text-right font-medium">Avg entry</th>
              <th className="px-4 py-2 text-right font-medium">Market value</th>
              <th className="px-4 py-2 text-right font-medium">Unrealized P/L</th>
              <th className="px-4 py-2 text-right font-medium" />
            </tr>
          </thead>
          <tbody>
            {positions.data.map((p) => {
              const pnlClass = cn(
                "px-4 py-2 text-right font-mono",
                p.unrealized_pl > 0
                  ? "text-bull"
                  : p.unrealized_pl < 0
                    ? "text-bear"
                    : "text-secondary",
              );
              const isClosing =
                close.isPending && close.variables === p.symbol;
              return (
                <tr
                  key={p.symbol}
                  className="border-b border-border last:border-0 hover:bg-elevated"
                >
                  <td className="px-4 py-2 font-mono font-medium text-primary">
                    <Link
                      href={`/ticker/${encodeURIComponent(p.symbol)}`}
                      className="flex items-center gap-2 hover:text-accent"
                    >
                      <TickerLogo ticker={p.symbol} size={20} />
                      {p.symbol}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-primary">
                    {p.qty}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-primary">
                    {formatUsd(p.avg_entry_price)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-primary">
                    {formatUsd(p.market_value)}
                  </td>
                  <td className={pnlClass}>{formatUsd(p.unrealized_pl)}</td>
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
                      className="rounded border border-border-strong bg-elevated px-2 py-0.5 text-xs font-medium text-secondary hover:bg-input hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
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
        <p className="border-t border-border px-4 py-2 text-xs text-bear">
          Close failed:{" "}
          {close.error instanceof Error ? close.error.message : "unknown error"}
        </p>
      )}
    </div>
  );
}
