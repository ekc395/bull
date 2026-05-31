"use client";

// TradingView-style technical-rating speedometer: a 180° dial split into five
// zones (Strong sell → Strong buy) with a needle pointing at the composite score.
// Driven by computeTechnicalRating(); summary only, not investment advice.

import { cn } from "@/lib/utils";
import type { TechnicalRating } from "@/lib/technicalRating";

const CX = 100;
const CY = 100;
const R = 78;
const STROKE = 16;

// Left→right along the top semicircle. Angles are measured CCW from +x axis,
// so 180° is the left tip, 90° the top, 0° the right tip.
const ZONES = [
  { from: 144, to: 180, color: "#EF5350" }, // strong sell
  { from: 108, to: 144, color: "#E0857F" }, // sell
  { from: 72, to: 108, color: "#787B86" }, // neutral
  { from: 36, to: 72, color: "#6FB89F" }, // buy
  { from: 0, to: 36, color: "#26A69A" }, // strong buy
];

function polar(angleDeg: number, r: number = R) {
  const a = (angleDeg * Math.PI) / 180;
  return { x: CX + r * Math.cos(a), y: CY - r * Math.sin(a) };
}

function arc(fromDeg: number, toDeg: number) {
  const start = polar(toDeg); // higher angle (more left)
  const end = polar(fromDeg); // lower angle (more right)
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${R} ${R} 0 0 1 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
}

function labelColor(label: TechnicalRating["label"]) {
  if (label === "Strong buy" || label === "Buy") return "text-bull";
  if (label === "Strong sell" || label === "Sell") return "text-bear";
  return "text-secondary";
}

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

export function TechnicalsGauge({ rating }: { rating: TechnicalRating }) {
  // score -1..1 → needle angle 180..0 (left=sell, right=buy).
  const needleAngle = 90 * (1 - clamp(rating.score, -1, 1));
  const tip = polar(needleAngle, R - 8);

  return (
    <section className="rounded-md border border-border bg-panel p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Technical rating
        </h3>
        <span className="text-[11px] text-muted">
          {rating.total} signal{rating.total === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mx-auto mt-3 max-w-[260px]">
        <svg
          viewBox="0 0 200 116"
          className="w-full"
          role="img"
          aria-label={`Technical rating: ${rating.label}`}
        >
          {ZONES.map((z) => (
            <path
              key={z.from}
              d={arc(z.from, z.to)}
              stroke={z.color}
              strokeWidth={STROKE}
              fill="none"
            />
          ))}
          {/* needle */}
          <line
            x1={CX}
            y1={CY}
            x2={tip.x}
            y2={tip.y}
            stroke="#D1D4DC"
            strokeWidth={3}
            strokeLinecap="round"
          />
          <circle cx={CX} cy={CY} r={5} fill="#D1D4DC" />
        </svg>
      </div>

      <p
        className={cn(
          "text-center text-lg font-semibold",
          labelColor(rating.label),
        )}
      >
        {rating.label}
      </p>

      <div className="mt-3 grid grid-cols-3 border-t border-border pt-3 text-center">
        <Count label="Sell" value={rating.sell} className="text-bear" />
        <Count
          label="Neutral"
          value={rating.neutral}
          className="text-secondary"
        />
        <Count label="Buy" value={rating.buy} className="text-bull" />
      </div>
    </section>
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
