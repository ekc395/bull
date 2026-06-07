"use client";

// Technical-rating speedometer: wraps the shared RatingGauge dial with a
// Sell / Neutral / Buy tally. Driven by computeTechnicalRating(); summary only.

import { RatingGauge } from "@/components/RatingGauge";
import { cn } from "@/lib/utils";
import type { TechnicalRating } from "@/lib/technicalRating";

// Strong sell → strong buy: red → maroon → purple → indigo → blue.
const TECHNICALS_PALETTE = [
  "#F23645",
  "#9C3A5A",
  "#6E3C9E",
  "#3D52E8",
  "#2962FF",
] as const;

export function TechnicalsGauge({ rating }: { rating: TechnicalRating }) {
  return (
    <RatingGauge
      title="Technical rating"
      topRight={`${rating.total} signal${rating.total === 1 ? "" : "s"}`}
      score={rating.score}
      label={rating.label}
      palette={TECHNICALS_PALETTE}
    >
      <div className="mt-3 grid grid-cols-3 border-t border-border pt-3 text-center">
        <Count label="Sell" value={rating.sell} className="text-bear" />
        <Count
          label="Neutral"
          value={rating.neutral}
          className="text-secondary"
        />
        <Count label="Buy" value={rating.buy} className="text-bull" />
      </div>
    </RatingGauge>
  );
}

function Count({
  label,
  value,
  className,
}: {
  label: string;
  value: number;
  className: string;
}) {
  return (
    <div>
      <div
        className={cn(
          "font-mono text-base font-semibold tabular-nums",
          className,
        )}
      >
        {value}
      </div>
      <div className="text-[11px] uppercase tracking-wide text-muted">
        {label}
      </div>
    </div>
  );
}
