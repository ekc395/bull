// "Execute paper trade" button. HOLD-guards (renders disabled with explanation),
// confirms via dialog reinforcing paper-only. Amount input supports either
// dollars (notional) or shares (qty); leaving it blank falls back to the
// server-side equity-percentage default.
"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";
import { useExecuteOrder } from "@/lib/queries";
import type { VerdictResponse } from "@/types/api";

type AmountMode = "dollars" | "shares";

export function ExecuteOrderButton({ verdict }: { verdict: VerdictResponse }) {
  const execute = useExecuteOrder();
  const [mode, setMode] = useState<AmountMode>("dollars");
  const [amount, setAmount] = useState<string>("");

  if (verdict.action === "HOLD") {
    return (
      <div className="rounded-md border border-border bg-panel p-3 text-xs text-secondary">
        HOLD verdict — no order to execute. Wait for the next trading day or
        run a fresh analysis.
      </div>
    );
  }

  const verb = verdict.action === "BUY" ? "Buy" : "Sell";
  const tone =
    verdict.action === "BUY"
      ? "bg-bull hover:brightness-110"
      : "bg-bear hover:brightness-110";

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
    <div className="space-y-2 rounded-md border border-border bg-panel p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[11px] uppercase tracking-wide text-muted">
            Amount
          </label>
          <div className="flex items-stretch overflow-hidden rounded-md border border-border-strong bg-elevated">
            <div className="flex">
              <button
                type="button"
                onClick={() => setMode("dollars")}
                className={cn(
                  "px-2 text-xs font-medium transition-colors",
                  mode === "dollars"
                    ? "bg-input text-primary"
                    : "text-muted hover:text-primary",
                )}
                aria-pressed={mode === "dollars"}
              >
                $
              </button>
              <button
                type="button"
                onClick={() => setMode("shares")}
                className={cn(
                  "border-l border-border-strong px-2 text-xs font-medium transition-colors",
                  mode === "shares"
                    ? "bg-input text-primary"
                    : "text-muted hover:text-primary",
                )}
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
              className="w-28 border-l border-border-strong bg-transparent px-2 py-1 text-sm text-primary placeholder:text-muted focus:outline-none"
            />
          </div>
        </div>

        <button
          type="button"
          disabled={execute.isPending || !amountValid}
          onClick={handleSubmit}
          className={cn(
            "rounded-md px-4 py-2 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            tone,
          )}
        >
          {execute.isPending
            ? "Submitting…"
            : `${verb} ${verdict.ticker} (paper)`}
        </button>
        <span className="text-xs italic text-muted">
          Paper trade · not financial advice
        </span>
      </div>

      {!amountValid && (
        <p className="text-xs text-bear">
          Amount must be a positive number, or leave blank to use the default.
        </p>
      )}
      {execute.isError && (
        <p className="text-xs text-bear">
          {execute.error instanceof Error
            ? execute.error.message
            : "Order failed."}
        </p>
      )}
      {execute.isSuccess && execute.data && (
        <p className="text-xs text-bull">
          Order submitted · status: {execute.data.status} · id{" "}
          <span className="font-mono">{execute.data.alpaca_order_id}</span>
        </p>
      )}
    </div>
  );
}
