// User-selected holding period (short | medium | long). Drives the prompt
// variant and tool windows in the agent. Persisted in localStorage so the
// dashboard remembers the choice; URL `?tf=` on the ticker page wins for
// shareability.

"use client";

import { useCallback, useEffect, useState } from "react";

import type { Timeframe } from "@/types/api";

const STORAGE_KEY = "bull.timeframe";
const DEFAULT: Timeframe = "medium";
const VALID: readonly Timeframe[] = ["short", "medium", "long"] as const;

export function isTimeframe(value: unknown): value is Timeframe {
  return typeof value === "string" && (VALID as readonly string[]).includes(value);
}

export function coerceTimeframe(value: unknown, fallback: Timeframe = DEFAULT): Timeframe {
  return isTimeframe(value) ? value : fallback;
}

// Reads the saved choice from localStorage, falling back to "medium". The
// initial render returns the default to avoid an SSR/CSR hydration mismatch;
// the stored value is applied on mount.
export function useTimeframe(): [Timeframe, (next: Timeframe) => void] {
  const [value, setValue] = useState<Timeframe>(DEFAULT);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (isTimeframe(raw)) setValue(raw);
    } catch {
      // localStorage unavailable (private mode, blocked) — keep the default.
    }
  }, []);

  const update = useCallback((next: Timeframe) => {
    setValue(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore — purely a persistence convenience.
    }
  }, []);

  return [value, update];
}

export const TIMEFRAMES = VALID;
export const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  short: "Short",
  medium: "Medium",
  long: "Long",
};
export const TIMEFRAME_HINTS: Record<Timeframe, string> = {
  short: "days to a few weeks",
  medium: "one to six months",
  long: "six months to multi-year",
};
