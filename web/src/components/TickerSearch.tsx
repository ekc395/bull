"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Timeframe } from "@/types/api";

export function TickerSearch({ timeframe }: { timeframe?: Timeframe }) {
  const router = useRouter();
  const [value, setValue] = useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const sym = value.trim().toUpperCase();
    if (!sym) return;
    const qs = timeframe ? `?tf=${timeframe}` : "";
    router.push(`/ticker/${encodeURIComponent(sym)}${qs}`);
  }

  return (
    <form onSubmit={onSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value.toUpperCase())}
        placeholder="Enter ticker (e.g. NVDA)"
        className="flex-1 rounded-md border border-border bg-elevated px-3 py-2 text-sm text-primary placeholder:text-muted focus:border-accent focus:outline-none"
        maxLength={10}
        autoComplete="off"
        spellCheck={false}
      />
      <button
        type="submit"
        disabled={!value.trim()}
        className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        Analyze
      </button>
    </form>
  );
}
