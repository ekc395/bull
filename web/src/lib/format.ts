// Currency / percent formatters.

export const formatUsd = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export const formatPct = (n: number, digits = 1) =>
  `${(n * 100).toFixed(digits)}%`;

// Compact magnitude, e.g. 5_109_588_000_000 → "5.11T". No currency symbol.
export const formatCompact = (n: number) =>
  new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(n);
