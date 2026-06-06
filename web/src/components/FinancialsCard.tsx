"use client";

// TradingView-style "Financials" section: a 2×2 grid of panels, each with its
// own Annual / Quarterly toggle, built on recharts. Data from /financials
// (yfinance income statement + balance sheet + cash flow). Earnings estimates
// come from Finnhub when a key is set; otherwise only actual EPS dots render.
//
//   Performance         — Revenue + Net income bars ($, right axis) + Net
//                         margin % line (left axis)
//   Revenue → profit    — waterfall for the latest period
//   Debt & coverage     — Debt / Free cash flow / Cash & equivalents bars
//   Earnings            — Actual vs Estimate EPS scatter

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  Rectangle,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  usePlotArea,
  useYAxisScale,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";
import { useFinancials, useFundamentals } from "@/lib/queries";
import { formatCompact } from "@/lib/format";
import type { FinancialPeriod } from "@/types/api";

type Mode = "annual" | "quarterly";

const CHART_H = 200;

// Softer pastel palette to match the TradingView mockup (not the app's hard tokens).
const C = {
  revenue: "#4a8fe7",
  netIncome: "#2bb1a8",
  margin: "#f59e0b",
  debt: "#e84d6f",
  fcf: "#2bb1a8",
  cash: "#7c8cf0",
  up: "#2bb1a8",
  down: "#e84d6f",
  subtotal: "#4a8fe7",
  grid: "#1f1f1f",
  axis: "#787b86",
};

// Chart layout / geometry (recharts props)
const CHART_MARGIN = { top: 6, right: 4, bottom: 0, left: 4 };
// Waterfall needs extra bottom room for two-line stage labels.
const WATERFALL_MARGIN = { ...CHART_MARGIN, bottom: 14 };
const Y_AXIS_WIDTH = 46; // $ / EPS axis gutter, px
const PCT_AXIS_WIDTH = 42; // net-margin % axis gutter, px
const BAR_RADIUS: [number, number, number, number] = [1, 1, 0, 0]; // rounded bar tops
const ZERO_LINE_OPACITY = 0.4; // baseline ReferenceLine at y = 0
const DASH = "3 3"; // dashed stroke (connectors + scatter cursor)
const AXIS_FONT_PX = 10;

// Waterfall stage labels (wrap onto up to two lines)
const STAGE_LABEL_FONT_PX = 9;
const STAGE_LABEL_LINE_PX = 10; // vertical gap between wrapped lines
const STAGE_LABEL_TOP_PX = 8; // gap below the axis before the first line
const WATERFALL_AXIS_HEIGHT = 28;

// Waterfall connectors
const BAR_WIDTH_RATIO = 0.8; // bar fills ~80% of its category band (10% gap each side)
const CONNECTOR_OPACITY = 0.7;

// Series marks
const MARGIN_LINE_WIDTH = 2;
const MARGIN_DOT_RADIUS = 2.5;
const ESTIMATE_RING_WIDTH = 1.5;

// Display precision + compact-money units (descending)
const DECIMALS = 2;
const MONEY_UNITS: readonly (readonly [number, string])[] = [
  [1e12, "T"],
  [1e9, "B"],
  [1e6, "M"],
  [1e3, "K"],
];

const MINUS = "−"; // proper minus sign, matches the mockup

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n < 0 ? MINUS : "";
  const abs = Math.abs(n);
  for (const [d, u] of MONEY_UNITS) {
    if (abs >= d) return `${sign}${(abs / d).toFixed(DECIMALS)} ${u} USD`;
  }
  return `${sign}${abs.toFixed(DECIMALS)} USD`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n < 0 ? MINUS : ""}${Math.abs(n).toFixed(DECIMALS)}%`;
}

function fmtEps(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n < 0 ? MINUS : ""}${Math.abs(n).toFixed(DECIMALS)} USD`;
}

function fmtDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// ─── Card shell ──────────────────────────────────────────────────────────────

export function FinancialsCard({ ticker }: { ticker: string }) {
  const { data } = useFinancials(ticker);
  const { data: fundamentals } = useFundamentals(ticker);
  if (!data) return null;

  const pickSeries = (mode: Mode): FinancialPeriod[] => {
    const primary = mode === "annual" ? data.annual : data.quarterly;
    if (primary.length > 0) return primary;
    return mode === "annual" ? data.quarterly : data.annual;
  };

  if (data.annual.length === 0 && data.quarterly.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="border-b border-border px-4 py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Financials
        </h3>
      </div>
      <div className="grid gap-3 p-3 sm:grid-cols-2">
        <PerformancePanel pickSeries={pickSeries} />
        <WaterfallPanel pickSeries={pickSeries} />
        <DebtPanel pickSeries={pickSeries} />
        <EarningsPanel
          pickSeries={pickSeries}
          nextDate={fundamentals?.earnings_date}
        />
      </div>
    </div>
  );
}

type PanelProps = { pickSeries: (mode: Mode) => FinancialPeriod[] };

// ─── Panel wrapper ───────────────────────────────────────────────────────────

function Panel({
  title,
  mode,
  setMode,
  legend,
  right,
  children,
}: {
  title: string;
  mode: Mode;
  setMode: (m: Mode) => void;
  legend?: { color: string; label: string; hollow?: boolean }[];
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-border bg-app/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <h4 className="truncate text-[12px] font-medium text-secondary">
            {title}
          </h4>
          {right}
        </div>
        <div className="flex gap-1">
          {(["annual", "quarterly"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn(
                "rounded px-2 py-0.5 text-[11px] font-medium capitalize transition-colors",
                mode === m
                  ? "bg-elevated text-primary"
                  : "text-muted hover:text-secondary",
              )}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      {children}
      {legend && (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[10px] text-muted">
          {legend.map((l) => (
            <span key={l.label} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={
                  l.hollow
                    ? { border: `1.5px solid ${l.color}` }
                    : { background: l.color }
                }
              />
              {l.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function NoData() {
  return (
    <div
      className="flex items-center justify-center text-[11px] text-muted"
      style={{ height: CHART_H }}
    >
      No data
    </div>
  );
}

const axisTick = { fill: C.axis, fontSize: AXIS_FONT_PX };
const cursorFill = { fill: "#ffffff", fillOpacity: 0.04 };

// ─── Tooltip ─────────────────────────────────────────────────────────────────

function Box({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded border border-border bg-elevated px-2.5 py-1.5 text-[11px] shadow-lg">
      {children}
    </div>
  );
}

function Dot({ color, hollow }: { color: string; hollow?: boolean }) {
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={hollow ? { border: `1.5px solid ${color}` } : { background: color }}
    />
  );
}

// ─── Performance ─────────────────────────────────────────────────────────────

function PerformancePanel({ pickSeries }: PanelProps) {
  const [mode, setMode] = useState<Mode>("annual");
  const series = pickSeries(mode);
  const rows = series.map((p) => ({
    period: p.period,
    revenue: p.revenue,
    net_income: p.net_income,
    margin:
      p.revenue && p.net_income != null && p.revenue !== 0
        ? (p.net_income / p.revenue) * 100
        : null,
  }));
  const hasData = rows.some((r) => r.revenue != null);

  return (
    <Panel
      title="Performance"
      mode={mode}
      setMode={setMode}
      legend={[
        { color: C.revenue, label: "Revenue" },
        { color: C.netIncome, label: "Net income" },
        { color: C.margin, label: "Net margin %" },
      ]}
    >
      {!hasData ? (
        <NoData />
      ) : (
        <ResponsiveContainer width="100%" height={CHART_H}>
          <ComposedChart data={rows} margin={CHART_MARGIN}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="period" tick={axisTick} tickLine={false} axisLine={{ stroke: C.grid }} />
            <YAxis
              yAxisId="pct"
              orientation="left"
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={PCT_AXIS_WIDTH}
              tickFormatter={(v: number) => `${v}%`}
            />
            <YAxis
              yAxisId="usd"
              orientation="right"
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={Y_AXIS_WIDTH}
              tickFormatter={(v: number) => formatCompact(v)}
            />
            <ReferenceLine yAxisId="usd" y={0} stroke={C.axis} strokeOpacity={ZERO_LINE_OPACITY} />
            <Tooltip cursor={cursorFill} content={<PerformanceTip />} />
            <Bar yAxisId="usd" dataKey="revenue" fill={C.revenue} radius={BAR_RADIUS} />
            <Bar yAxisId="usd" dataKey="net_income" fill={C.netIncome} radius={BAR_RADIUS} />
            <Line
              yAxisId="pct"
              type="linear"
              dataKey="margin"
              stroke={C.margin}
              strokeWidth={MARGIN_LINE_WIDTH}
              dot={{ r: MARGIN_DOT_RADIUS, fill: C.margin, strokeWidth: 0 }}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function PerformanceTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <Box>
      <div className="flex items-center gap-2">
        <Dot color={C.revenue} /> Revenue
        <span className="ml-auto pl-3 font-mono">{fmtMoney(r.revenue)}</span>
      </div>
      <div className="flex items-center gap-2">
        <Dot color={C.netIncome} /> Net income
        <span className="ml-auto pl-3 font-mono">{fmtMoney(r.net_income)}</span>
      </div>
      <div className="flex items-center gap-2">
        <Dot color={C.margin} /> Net margin
        <span className="ml-auto pl-3 font-mono">{fmtPct(r.margin)}</span>
      </div>
    </Box>
  );
}

// ─── Revenue → profit conversion (waterfall) ─────────────────────────────────

type Stage = {
  name: string; // full label for the tooltip
  label: string; // short axis label (wraps onto up to two lines)
  base: number;
  value: number; // visible height (always >= 0)
  delta: number; // signed change for the tooltip
  endLevel: number; // running cumulative at this stage's right edge (connectors)
  color: string;
};

function buildWaterfall(p: FinancialPeriod): Stage[] | null {
  const { revenue, gross_profit, operating_income, non_operating, net_income } = p;
  if (revenue == null || net_income == null) return null;
  const gp = gross_profit ?? revenue;
  const oi = operating_income ?? gp;
  const afterNonOp = oi + (non_operating ?? 0);

  const flow = (name: string, from: number, to: number, label = name): Stage => ({
    name,
    label,
    base: Math.min(from, to),
    value: Math.abs(to - from),
    delta: to - from,
    endLevel: to,
    color: to >= from ? C.up : C.down,
  });
  const subtotal = (name: string, level: number, label = name): Stage => ({
    name,
    label,
    base: Math.min(0, level),
    value: Math.abs(level),
    delta: level,
    endLevel: level,
    color: C.subtotal,
  });

  return [
    subtotal("Revenue", revenue),
    flow("COGS", revenue, gp),
    subtotal("Gross profit", gp),
    flow("Op expenses", gp, oi),
    subtotal("Op income", oi),
    flow("Non-Op income/expenses", oi, afterNonOp, "Non-op"),
    flow("Taxes & Other", afterNonOp, net_income, "Taxes"),
    subtotal("Net income", net_income),
  ];
}

function WaterfallPanel({ pickSeries }: PanelProps) {
  const [mode, setMode] = useState<Mode>("annual");
  const series = pickSeries(mode);
  const latest = series.length ? series[series.length - 1] : null;
  const stages = latest ? buildWaterfall(latest) : null;

  return (
    <Panel title="Revenue to profit conversion" mode={mode} setMode={setMode}>
      {!stages ? (
        <NoData />
      ) : (
        <ResponsiveContainer width="100%" height={CHART_H}>
          <BarChart data={stages} margin={WATERFALL_MARGIN}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis
              dataKey="label"
              tick={<WaterfallTick />}
              interval={0}
              tickLine={false}
              axisLine={{ stroke: C.grid }}
              height={WATERFALL_AXIS_HEIGHT}
            />
            <YAxis
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={Y_AXIS_WIDTH}
              tickFormatter={(v: number) => formatCompact(v)}
            />
            <Tooltip cursor={cursorFill} content={<WaterfallTip />} />
            <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
            <Bar
              dataKey="value"
              stackId="w"
              isAnimationActive={false}
              // Per-stage color (subtotal / increase / decrease) via shape — the
              // v3 replacement for the deprecated <Cell> child.
              shape={(props: any) => (
                <Rectangle
                  {...props}
                  radius={BAR_RADIUS}
                  fill={props.payload.color}
                />
              )}
            />
            <WaterfallConnectors stages={stages} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function WaterfallTick({ x, y, payload }: any) {
  const words = String(payload.value).split(" ");
  // payload.value is the stage `label` (XAxis dataKey="label") — short text
  // chosen to fit the narrow bar band; the tooltip still shows the full name.
  return (
    <g transform={`translate(${x},${y + STAGE_LABEL_TOP_PX})`}>
      {words.map((w: string, i: number) => (
        <text
          key={i}
          x={0}
          y={i * STAGE_LABEL_LINE_PX}
          textAnchor="middle"
          fill={C.axis}
          fontSize={STAGE_LABEL_FONT_PX}
        >
          {w}
        </text>
      ))}
    </g>
  );
}

// Dashed horizontal links from each stage's running total to the next bar,
// like the TradingView waterfall. recharts 3.x exposes the plot area + y-scale
// via hooks; x positions are evenly-spaced category bands we compute directly.
function WaterfallConnectors({ stages }: { stages: Stage[] }) {
  const plot = usePlotArea();
  const yScale = useYAxisScale();
  if (!plot || !yScale) return null;
  const n = stages.length;
  const band = plot.width / n;
  const halfBar = (band * BAR_WIDTH_RATIO) / 2; // bar edge from its band center

  const lines: React.ReactNode[] = [];
  for (let i = 0; i < n - 1; i++) {
    const cxHere = plot.x + (i + 0.5) * band; // band center of stage i
    const cxNext = plot.x + (i + 1.5) * band; // band center of stage i + 1
    const y = yScale(stages[i].endLevel);
    if (y == null) continue;
    lines.push(
      <line
        key={i}
        x1={cxHere + halfBar}
        y1={y}
        x2={cxNext - halfBar}
        y2={y}
        stroke={C.axis}
        strokeDasharray={DASH}
        strokeWidth={1}
        strokeOpacity={CONNECTOR_OPACITY}
      />,
    );
  }
  return <g>{lines}</g>;
}

function WaterfallTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const s: Stage = payload[payload.length - 1].payload;
  return (
    <Box>
      <span className="text-secondary">{s.name}</span>
      <span className="ml-3 font-mono">{fmtMoney(s.delta)}</span>
    </Box>
  );
}

// ─── Debt level and coverage ─────────────────────────────────────────────────

function DebtPanel({ pickSeries }: PanelProps) {
  const [mode, setMode] = useState<Mode>("annual");
  const series = pickSeries(mode);
  const rows = series.map((p) => ({
    period: p.period,
    debt: p.total_debt,
    fcf: p.free_cash_flow,
    cash: p.cash,
  }));
  const hasData = rows.some(
    (r) => r.debt != null || r.fcf != null || r.cash != null,
  );

  return (
    <Panel
      title="Debt level and coverage"
      mode={mode}
      setMode={setMode}
      legend={[
        { color: C.debt, label: "Debt" },
        { color: C.fcf, label: "Free cash flow" },
        { color: C.cash, label: "Cash & equivalents" },
      ]}
    >
      {!hasData ? (
        <NoData />
      ) : (
        <ResponsiveContainer width="100%" height={CHART_H}>
          <BarChart data={rows} margin={CHART_MARGIN}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="period" tick={axisTick} tickLine={false} axisLine={{ stroke: C.grid }} />
            <YAxis
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={Y_AXIS_WIDTH}
              tickFormatter={(v: number) => formatCompact(v)}
            />
            <ReferenceLine y={0} stroke={C.axis} strokeOpacity={ZERO_LINE_OPACITY} />
            <Tooltip cursor={cursorFill} content={<DebtTip />} />
            <Bar dataKey="debt" fill={C.debt} radius={BAR_RADIUS} />
            <Bar dataKey="fcf" fill={C.fcf} radius={BAR_RADIUS} />
            <Bar dataKey="cash" fill={C.cash} radius={BAR_RADIUS} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function DebtTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <Box>
      <div className="flex items-center gap-2">
        <Dot color={C.debt} /> Debt
        <span className="ml-auto pl-3 font-mono">{fmtMoney(r.debt)}</span>
      </div>
      <div className="flex items-center gap-2">
        <Dot color={C.fcf} /> Free cash flow
        <span className="ml-auto pl-3 font-mono">{fmtMoney(r.fcf)}</span>
      </div>
      <div className="flex items-center gap-2">
        <Dot color={C.cash} /> Cash &amp; equivalents
        <span className="ml-auto pl-3 font-mono">{fmtMoney(r.cash)}</span>
      </div>
    </Box>
  );
}

// ─── Earnings ────────────────────────────────────────────────────────────────

function EarningsPanel({
  pickSeries,
  nextDate,
}: PanelProps & { nextDate?: string | null }) {
  const [mode, setMode] = useState<Mode>("annual");
  const series = pickSeries(mode);
  const points = series.map((p) => ({
    period: p.period,
    report_date: p.report_date,
    eps: p.eps,
    estimate: p.estimate,
    surprise_pct: p.surprise_pct,
  }));
  const actual = points.filter((p) => p.eps != null).map((p) => ({ ...p, value: p.eps }));
  const estimate = points
    .filter((p) => p.estimate != null)
    .map((p) => ({ ...p, value: p.estimate }));
  const next = fmtDate(nextDate);

  return (
    <Panel
      title="Earnings"
      mode={mode}
      setMode={setMode}
      right={
        next ? (
          <span className="truncate text-[10px] text-muted">Next: {next}</span>
        ) : undefined
      }
      legend={[
        { color: C.fcf, label: "Actual" },
        { color: C.axis, label: "Estimate", hollow: true },
      ]}
    >
      {actual.length === 0 && estimate.length === 0 ? (
        <NoData />
      ) : (
        <ResponsiveContainer width="100%" height={CHART_H}>
          <ScatterChart margin={CHART_MARGIN}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis
              dataKey="period"
              type="category"
              allowDuplicatedCategory={false}
              tick={axisTick}
              tickLine={false}
              axisLine={{ stroke: C.grid }}
            />
            <YAxis
              dataKey="value"
              type="number"
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={Y_AXIS_WIDTH}
              tickFormatter={(v: number) => v.toFixed(DECIMALS)}
            />
            <ReferenceLine y={0} stroke={C.axis} strokeOpacity={ZERO_LINE_OPACITY} />
            <Tooltip
              cursor={{ strokeDasharray: DASH, stroke: C.axis }}
              content={<EarningsTip />}
            />
            <Scatter data={actual} fill={C.fcf} />
            <Scatter
              data={estimate}
              fill="transparent"
              stroke={C.axis}
              strokeWidth={ESTIMATE_RING_WIDTH}
            />
          </ScatterChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function EarningsTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const date = fmtDate(r.report_date);
  const delta =
    r.eps != null && r.estimate != null ? r.eps - r.estimate : null;
  return (
    <Box>
      {date && (
        <div className="text-muted">
          Date <span className="text-secondary">{date}</span>
        </div>
      )}
      {r.eps != null && (
        <div>
          Actual <span className="font-mono">{fmtEps(r.eps)}</span>
        </div>
      )}
      {r.estimate != null && (
        <div>
          Estimate <span className="font-mono">{fmtEps(r.estimate)}</span>
        </div>
      )}
      {delta != null && (
        <div style={{ color: delta >= 0 ? C.up : C.down }}>
          Surprise {fmtEps(delta)}
          {r.surprise_pct != null && ` (${fmtPct(r.surprise_pct)})`}
        </div>
      )}
    </Box>
  );
}
