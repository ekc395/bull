"use client";

// Generic TradingView-style rating dial: a 180° speedometer split into five
// zones (Strong sell → Strong buy) with a needle at `score` (-1..1). Shared by
// the technicals and analyst gauges; callers supply the title, label, and an
// optional footer (counts, price targets, …) via children. Summary, not advice.

import { useId, type ReactNode } from "react";

const CX = 100;
const CY = 100;
const R = 78;
const STROKE = 16;

// Half-circle dial, angles measured CCW from +x: 180° = left tip (strong sell),
// 90° = top (neutral), 0° = right tip (strong buy).
const STRONG_SELL_ANGLE = 180;
const STRONG_BUY_ANGLE = 0;

// Score domain the needle maps onto the sweep.
const SCORE_MIN = -1;
const SCORE_MAX = 1;

// Unfilled remainder of the dial, past the needle.
const TRACK = "#3C3F47";
// Needle + hub color (the `primary` token).
const NEEDLE = "#D1D4DC";

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

// Sample the palette ramp at t (0 = first stop … 1 = last), interpolating in RGB
// between the two surrounding stops. Used to color the verdict label at the
// needle position so it tracks the same gradient drawn on the arc.
function colorAt(palette: readonly string[], t: number): string {
  const n = palette.length - 1;
  const x = clamp(t, 0, 1) * n;
  const i = Math.min(Math.floor(x), n - 1);
  const f = x - i;
  const a = hexToRgb(palette[i]);
  const b = hexToRgb(palette[i + 1]);
  const mix = (k: 0 | 1 | 2) => Math.round(a[k] + (b[k] - a[k]) * f);
  return `rgb(${mix(0)}, ${mix(1)}, ${mix(2)})`;
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

export function RatingGauge({
  title,
  topRight,
  score,
  label,
  palette,
  children,
}: {
  title: string;
  topRight?: ReactNode;
  score: number; // -1 (strong sell) .. +1 (strong buy)
  label: string;
  palette: readonly string[]; // strong-sell → strong-buy color ramp
  children?: ReactNode;
}) {
  const clamped = clamp(score, SCORE_MIN, SCORE_MAX);
  // 0 (strong sell) .. 1 (strong buy) — position along the sweep.
  const t = (clamped - SCORE_MIN) / (SCORE_MAX - SCORE_MIN);
  const needleAngle =
    STRONG_SELL_ANGLE + (STRONG_BUY_ANGLE - STRONG_SELL_ANGLE) * t;
  const tip = polar(needleAngle, R - 8);
  const gradientId = useId();

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
          <defs>
            <linearGradient
              id={gradientId}
              gradientUnits="userSpaceOnUse"
              x1={CX - R}
              y1={CY}
              x2={CX + R}
              y2={CY}
            >
              {palette.map((color, i) => (
                <stop
                  key={i}
                  offset={i / (palette.length - 1)}
                  stopColor={color}
                />
              ))}
            </linearGradient>
          </defs>
          {/* Full track, then the colored ramp lit up only to the needle. */}
          <path
            d={arc(STRONG_BUY_ANGLE, STRONG_SELL_ANGLE)}
            stroke={TRACK}
            strokeWidth={STROKE}
            strokeLinecap="round"
            fill="none"
          />
          <path
            d={arc(needleAngle, STRONG_SELL_ANGLE)}
            stroke={`url(#${gradientId})`}
            strokeWidth={STROKE}
            strokeLinecap="round"
            fill="none"
          />
          <line
            x1={CX}
            y1={CY}
            x2={tip.x}
            y2={tip.y}
            stroke={NEEDLE}
            strokeWidth={3}
            strokeLinecap="round"
          />
          <circle cx={CX} cy={CY} r={5} fill={NEEDLE} />
        </svg>
      </div>

      <p
        className="text-center text-lg font-semibold"
        style={{ color: colorAt(palette, t) }}
      >
        {label}
      </p>

      {children}
    </section>
  );
}
