// "Execute paper trade" button. HOLD-guards (renders disabled with explanation),
// confirms via dialog reinforcing paper-only. Amount input supports either
// dollars (notional) or shares (qty); leaving it blank falls back to the
// server-side equity-percentage default.
"use client";

import { useState } from "react";

import { useExecuteOrder } from "@/lib/queries";
import type { VerdictResponse } from "@/types/api";

type AmountMode = "dollars" | "shares";

export function ExecuteOrderButton({ verdict }: { verdict: VerdictResponse }) {
  const execute = useExecuteOrder();
  const [mode, setMode] = useState<AmountMode>("dollars");
  const [amount, setAmount] = useState<string>("");

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

  const parsed = amount.trim() === "" ? null : Number(amount);
  const amountValid = parsed === null || (Number.isFinite(parsed) && parsed > 0);

  const handleSubmit = () => {
    if (!amountValid) return;
    const sizeText =
      parsed === null
        ? "the default position size"
        : mode === "dollars"
          ? `$${parsed.toLocaleString()}`
          : `${parsed} share${parsed === 1 ? "" : "s"}`;
    const msg =
      `Place paper ${verb.toUpperCase()} order for ${verdict.ticker} (${sizeText})?\n\n` +
      `This will submit a market-day order via Alpaca paper trading.\n` +
      `Not financial advice.`;
    if (!confirm(msg)) return;
    const req: { verdict_id: number; notional?: number; qty?: number } = {
      verdict_id: verdict.id,
    };
    if (parsed !== null) {
      if (mode === "dollars") req.notional = parsed;
      else req.qty = parsed;
    }
    execute.mutate(req);
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-600">Amount</label>
          <div className="flex items-stretch overflow-hidden rounded-md border border-slate-300 bg-white shadow-sm">
            <div className="flex">
              <button
                type="button"
                onClick={() => setMode("dollars")}
                className={`px-2 text-xs font-medium transition ${
                  mode === "dollars"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                }`}
                aria-pressed={mode === "dollars"}
              >
                $
              </button>
              <button
                type="button"
                onClick={() => setMode("shares")}
                className={`border-l border-slate-300 px-2 text-xs font-medium transition ${
                  mode === "shares"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                }`}
                aria-pressed={mode === "shares"}
              >
                shares
              </button>
            </div>
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step={mode === "dollars" ? "0.01" : "0.0001"}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={mode === "dollars" ? "default" : "e.g. 10"}
              className="w-28 border-l border-slate-300 px-2 py-1 text-sm focus:outline-none"
            />
          </div>
        </div>

        <button
          type="button"
          disabled={execute.isPending || !amountValid}
          onClick={handleSubmit}
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

      {!amountValid && (
        <p className="text-xs text-red-600">
          Amount must be a positive number, or leave blank to use the default.
        </p>
      )}
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
