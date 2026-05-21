// Alpaca paper account stats: equity, cash, buying power. Polls /account every 10s.
"use client";

import { formatUsd } from "@/lib/format";
import { useAccount } from "@/lib/queries";

export function AccountPanel() {
  const account = useAccount();

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
          Account (paper)
        </h2>
        <span className="text-[10px] uppercase tracking-wide text-slate-400">
          Alpaca
        </span>
      </div>

      {account.isLoading && (
        <p className="text-sm text-slate-500">Loading…</p>
      )}
      {account.isError && (
        <p className="text-sm text-red-600">
          {account.error instanceof Error
            ? account.error.message
            : "Failed to load account."}
        </p>
      )}
      {account.data && (
        <dl className="grid grid-cols-3 gap-3 text-sm">
          <Stat label="Equity" value={formatUsd(account.data.equity)} />
          <Stat label="Cash" value={formatUsd(account.data.cash)} />
          <Stat label="Buying power" value={formatUsd(account.data.buying_power)} />
        </dl>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-mono text-base font-semibold text-slate-900">{value}</dd>
    </div>
  );
}
