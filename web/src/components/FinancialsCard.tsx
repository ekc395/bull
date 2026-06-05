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
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
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

const MINUS = "−"; // proper minus sign, matches the mockup

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n < 0 ? MINUS : "";
  const abs = Math.abs(n);
  for (const [d, u] of [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ] as const) {
    if (abs >= d) return `${sign}${(abs / d).toFixed(2)} ${u} USD`;
  }
  return `${sign}${abs.toFixed(2)} USD`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n < 0 ? MINUS : ""}${Math.abs(n).toFixed(2)}%`;
}

function fmtEps(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n < 0 ? MINUS : ""}${Math.abs(n).toFixed(2)} USD`;
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

const axisTick = { fill: C.axis, fontSize: 10 };
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
          <ComposedChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="period" tick={axisTick} tickLine={false} axisLine={{ stroke: C.grid }} />
            <YAxis
              yAxisId="pct"
              orientation="left"
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={42}
              tickFormatter={(v: number) => `${v}%`}
            />
            <YAxis
              yAxisId="usd"
              orientation="right"
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={46}
              tickFormatter={(v: number) => formatCompact(v)}
            />
            <ReferenceLine yAxisId="usd" y={0} stroke={C.axis} strokeOpacity={0.4} />
            <Tooltip cursor={cursorFill} content={<PerformanceTip />} />
            <Bar yAxisId="usd" dataKey="revenue" fill={C.revenue} radius={[1, 1, 0, 0]} />
            <Bar yAxisId="usd" dataKey="net_income" fill={C.netIncome} radius={[1, 1, 0, 0]} />
            <Line
              yAxisId="pct"
              type="linear"
              dataKey="margin"
              stroke={C.margin}
              strokeWidth={2}
              dot={{ r: 2.5, fill: C.margin, strokeWidth: 0 }}
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
  name: string;
  base: number;
  value: number; // visible height (always >= 0)
  delta: number; // signed change for the tooltip
  color: string;
};

function buildWaterfall(p: FinancialPeriod): Stage[] | null {
  const { revenue, gross_profit, operating_income, non_operating, net_income } = p;
  if (revenue == null || net_income == null) return null;
  const gp = gross_profit ?? revenue;
  const oi = operating_income ?? gp;
  const afterNonOp = oi + (non_operating ?? 0);

  const flow = (name: string, from: number, to: number): Stage => ({
    name,
    base: Math.min(from, to),
    value: Math.abs(to - from),
    delta: to - from,
    color: to >= from ? C.up : C.down,
  });
  const subtotal = (name: string, level: number): Stage => ({
    name,
    base: Math.min(0, level),
    value: Math.abs(level),
    delta: level,
    color: C.subtotal,
  });

  return [
    subtotal("Revenue", revenue),
    flow("COGS", revenue, gp),
    subtotal("Gross profit", gp),
    flow("Op expenses", gp, oi),
    subtotal("Op income", oi),
    flow("Non-Op income/expenses", oi, afterNonOp),
    flow("Taxes & Other", afterNonOp, net_income),
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
          <BarChart data={stages} margin={{ top: 6, right: 4, bottom: 14, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis
              dataKey="name"
              tick={<WaterfallTick />}
              interval={0}
              tickLine={false}
              axisLine={{ stroke: C.grid }}
              height={28}
            />
            <YAxis
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={46}
              tickFormatter={(v: number) => formatCompact(v)}
            />
            <Tooltip cursor={cursorFill} content={<WaterfallTip />} />
            <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="value" stackId="w" radius={[1, 1, 0, 0]} isAnimationActive={false}>
              {stages.map((s, i) => (
                <Cell key={i} fill={s.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function WaterfallTick({ x, y, payload }: any) {
  const words = String(payload.value).split(" ");
  return (
    <g transform={`translate(${x},${y + 8})`}>
      {words.map((w: string, i: number) => (
        <text
          key={i}
          x={0}
          y={i * 10}
          textAnchor="middle"
          fill={C.axis}
          fontSize={9}
        >
          {w}
        </text>
      ))}
    </g>
  );
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
          <BarChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="period" tick={axisTick} tickLine={false} axisLine={{ stroke: C.grid }} />
            <YAxis
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={46}
              tickFormatter={(v: number) => formatCompact(v)}
            />
            <ReferenceLine y={0} stroke={C.axis} strokeOpacity={0.4} />
            <Tooltip cursor={cursorFill} content={<DebtTip />} />
            <Bar dataKey="debt" fill={C.debt} radius={[1, 1, 0, 0]} />
            <Bar dataKey="fcf" fill={C.fcf} radius={[1, 1, 0, 0]} />
            <Bar dataKey="cash" fill={C.cash} radius={[1, 1, 0, 0]} />
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
          <ScatterChart margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
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
              width={46}
              tickFormatter={(v: number) => v.toFixed(2)}
            />
            <ReferenceLine y={0} stroke={C.axis} strokeOpacity={0.4} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3", stroke: C.axis }}
              content={<EarningsTip />}
            />
            <Scatter data={actual} fill={C.fcf} />
            <Scatter
              data={estimate}
              fill="transparent"
              stroke={C.axis}
              strokeWidth={1.5}
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
