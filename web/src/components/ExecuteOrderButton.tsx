// "Execute paper trade" button. HOLD-guards (renders disabled with explanation),
// confirms via dialog reinforcing paper-only.
"use client";

import { useExecuteOrder } from "@/lib/queries";
import type { VerdictResponse } from "@/types/api";

export function ExecuteOrderButton({ verdict }: { verdict: VerdictResponse }) {
  const execute = useExecuteOrder();

  if (verdict.action === "HOLD") {
    return (
      <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
        HOLD verdict — no order to execute. Wait for the next trading day or
        click below to force a fresh analysis.
      </div>
    );
  }

  const verb = verdict.action === "BUY" ? "Buy" : "Sell";
  const tone =
    verdict.action === "BUY"
      ? "bg-emerald-600 hover:bg-emerald-700"
      : "bg-rose-600 hover:bg-rose-700";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={execute.isPending}
          onClick={() => {
            const msg =
              `Place paper ${verb.toUpperCase()} order for ${verdict.ticker}?\n\n` +
              `This will submit a market-day notional order via Alpaca paper trading.\n` +
              `Not financial advice.`;
            if (confirm(msg)) {
              execute.mutate({ verdict_id: verdict.id });
            }
          }}
          className={`rounded-md px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50 ${tone}`}
        >
          {execute.isPending
            ? "Submitting…"
            : `${verb} ${verdict.ticker} (paper)`}
        </button>
        <span className="text-xs italic text-slate-500">
          Paper trade · not financial advice
        </span>
      </div>

      {execute.isError && (
        <p className="text-xs text-red-600">
          {execute.error instanceof Error
            ? execute.error.message
            : "Order failed."}
        </p>
      )}
      {execute.isSuccess && execute.data && (
        <p className="text-xs text-emerald-700">
          Order submitted · status: {execute.data.status} · id{" "}
          <span className="font-mono">{execute.data.alpaca_order_id}</span>
        </p>
      )}
    </div>
  );
}
