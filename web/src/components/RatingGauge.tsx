"use client";

// Generic TradingView-style rating dial: a 180° speedometer split into five
// zones (Strong sell → Strong buy) with a needle at `score` (-1..1). Shared by
// the technicals and analyst gauges; callers supply the title, label, and an
// optional footer (counts, price targets, …) via children. Summary, not advice.

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type GaugeTone = "bull" | "bear" | "neutral";

const CX = 100;
const CY = 100;
const R = 78;
const STROKE = 16;

// Angles measured CCW from +x: 180° = left tip, 90° = top, 0° = right tip.
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
  const start = polar(toDeg);
  const end = polar(fromDeg);
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${R} ${R} 0 0 1 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
}

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

function toneClass(t: GaugeTone) {
  if (t === "bull") return "text-bull";
  if (t === "bear") return "text-bear";
  return "text-secondary";
}

export function RatingGauge({
  title,
  topRight,
  score,
  label,
  labelTone,
  children,
}: {
  title: string;
  topRight?: ReactNode;
  score: number; // -1 (strong sell) .. +1 (strong buy)
  label: string;
  labelTone: GaugeTone;
  children?: ReactNode;
}) {
  const needleAngle = 90 * (1 - clamp(score, -1, 1));
  const tip = polar(needleAngle, R - 8);

  return (
    <section className="rounded-md border border-border bg-panel p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          {title}
        </h3>
        {topRight != null && (
          <span className="text-[11px] text-muted">{topRight}</span>
        )}
      </div>

      <div className="mx-auto mt-3 max-w-[260px]">
        <svg
          viewBox="0 0 200 116"
          className="w-full"
          role="img"
          aria-label={`${title}: ${label}`}
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

      <p className={cn("text-center text-lg font-semibold", toneClass(labelTone))}>
        {label}
      </p>

      {children}
    </section>
  );
}
