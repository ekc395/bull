"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import { TickerLogo } from "@/components/TickerLogo";
import type { Timeframe } from "@/types/api";

export function TickerSearch({ timeframe }: { timeframe?: Timeframe }) {
  const router = useRouter();
  const [value, setValue] = useState("");

  // Debounce the live logo preview so it doesn't fire a request per keystroke.
  const [preview, setPreview] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setPreview(value.trim()), 300);
    return () => clearTimeout(t);
  }, [value]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const sym = value.trim().toUpperCase();
    if (!sym) return;
    const qs = timeframe ? `?tf=${timeframe}` : "";
    router.push(`/ticker/${encodeURIComponent(sym)}${qs}`);
  }

  return (
    <form onSubmit={onSubmit} className="flex gap-2">
      <div className="relative flex-1">
        {preview && (
          <TickerLogo
            ticker={preview}
            size={20}
            className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2"
          />
        )}
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          placeholder="Enter ticker (e.g. NVDA)"
          className={cn(
            "w-full rounded-md border border-border bg-elevated py-2 text-sm text-primary placeholder:text-muted focus:outline-none",
            preview ? "pl-9 pr-3" : "px-3",
          )}
          maxLength={10}
          autoComplete="off"
          spellCheck={false}
        />
      </div>
      <button
        type="submit"
        disabled={!value.trim()}
        className="rounded-md border border-border-strong bg-elevated px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-input disabled:cursor-not-allowed disabled:opacity-50"
      >
        Analyze
      </button>
    </form>
  );
}
