// Currency / percent formatters.

export const formatUsd = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export const formatPct = (n: number, digits = 1) =>
  `${(n * 100).toFixed(digits)}%`;
