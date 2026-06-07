"use client";

// Analyst-rating speedometer: maps the consensus recommendation mean
// (1 = strong buy … 5 = strong sell) onto the shared RatingGauge, with the
// low / mean / high price targets as a footer. Data from /fundamentals.

import { RatingGauge } from "@/components/RatingGauge";
import { useFundamentals } from "@/lib/queries";
import { formatUsd } from "@/lib/format";

// Strong sell → strong buy: orange → amber → yellow-green → green → teal.
const ANALYST_PALETTE = [
  "#E8842E",
  "#E0A93A",
  "#C2C04A",
  "#5FB87C",
  "#26A69A",
] as const;

export function AnalystGauge({ ticker }: { ticker: string }) {
  const { data } = useFundamentals(ticker);
  const mean = data?.recommendation_mean;
  if (data == null || mean == null) return null;

  // mean 1..5 → score +1..-1 (3 = hold = 0).
  const score = (3 - mean) / 2;
  const label = data.recommendation_key
    ? titleCase(data.recommendation_key)
    : labelFromScore(score);

  const targets = [
    { label: "Low", value: data.analyst_target_low },
    { label: "Mean", value: data.analyst_target_mean },
    { label: "High", value: data.analyst_target_high },
  ].filter((t) => t.value != null) as { label: string; value: number }[];

  return (
    <RatingGauge
      title="Analyst rating"
      topRight={
        data.analyst_count != null ? `${data.analyst_count} analysts` : undefined
      }
      score={score}
      label={label}
      palette={ANALYST_PALETTE}
    >
      {targets.length > 0 && (
        <div className="mt-3 grid grid-cols-3 border-t border-border pt-3 text-center">
          {targets.map((t) => (
            <div key={t.label}>
              <div className="font-mono text-sm font-semibold tabular-nums text-primary">
                {formatUsd(t.value)}
              </div>
              <div className="text-[11px] uppercase tracking-wide text-muted">
                {t.label}
              </div>
            </div>
          ))}
        </div>
      )}
    </RatingGauge>
  );
}

function titleCase(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function labelFromScore(score: number): string {
  if (score >= 0.5) return "Strong buy";
  if (score >= 0.1) return "Buy";
  if (score > -0.1) return "Hold";
  if (score > -0.5) return "Sell";
  return "Strong sell";
}
