"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function TickerSearch() {
  const router = useRouter();
  const [value, setValue] = useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const sym = value.trim().toUpperCase();
    if (!sym) return;
    router.push(`/ticker/${encodeURIComponent(sym)}`);
  }

  return (
    <form onSubmit={onSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value.toUpperCase())}
        placeholder="Enter ticker (e.g. NVDA)"
        className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        maxLength={10}
        autoComplete="off"
        spellCheck={false}
      />
      <button
        type="submit"
        disabled={!value.trim()}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Analyze
      </button>
    </form>
  );
}
