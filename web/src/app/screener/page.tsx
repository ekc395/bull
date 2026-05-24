"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { useScreenerPreview, useScreenerRun } from "@/lib/queries";
import type {
  ScreenerCandidate,
  ScreenerPreviewResponse,
  ScreenerRunResponse,
} from "@/types/api";

type Phase = "idle" | "previewing" | "preview_ready" | "running" | "done";

export default function ScreenerPage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [preview, setPreview] = useState<ScreenerPreviewResponse | null>(null);
  const [result, setResult] = useState<ScreenerRunResponse | null>(null);

  const previewMut = useScreenerPreview();
  const runMut = useScreenerRun();

  const startPreview = () => {
    setPhase("previewing");
    setResult(null);
    previewMut.mutate(undefined, {
      onSuccess: (res) => {
        setPreview(res);
        setPhase("preview_ready");
      },
      onError: () => setPhase("idle"),
    });
  };

  const startRun = () => {
    if (!preview?.candidates.length) return;
    setPhase("running");
    runMut.mutate(
      { tickers: preview.candidates.map((c) => c.symbol) },
      {
        onSuccess: (res) => {
          setResult(res);
          setPhase("done");
        },
        onError: () => setPhase("preview_ready"),
      },
    );
  };

  const cancel = () => {
    setPreview(null);
    setPhase("idle");
  };

  return (
    <main className="container mx-auto max-w-6xl space-y-6 p-6">
      <header className="space-y-1">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">S&P 500 screener</h1>
          <Link href="/" className="text-sm text-slate-600 hover:underline">
            ← Dashboard
          </Link>
        </div>
        <p className="text-sm text-slate-600">
          Scans the S&P 500 for swing-trade BUY candidates using a free technical
          pre-filter (RSI, MACD, SMAs, volume), then runs Claude on the survivors.
        </p>
      </header>

      {phase === "idle" && (
        <div className="rounded-lg border bg-white p-6">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
            Step 1 — Free pre-filter
          </h2>
          <p className="mt-2 text-sm text-slate-700">
            Downloads 2 years of OHLCV for all ~500 constituents, computes indicators,
            and surfaces tickers passing all of: RSI 30–55, MACD&nbsp;hist&nbsp;&gt;&nbsp;0,
            close&nbsp;&gt;&nbsp;SMA-50, SMA-50&nbsp;&gt;&nbsp;SMA-200, volume&nbsp;&gt;&nbsp;20-day average.
          </p>
          <button
            type="button"
            onClick={startPreview}
            className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Run screen
          </button>
          {previewMut.isError && (
            <p className="mt-3 text-sm text-rose-600">
              Pre-filter failed: {(previewMut.error as Error).message}
            </p>
          )}
        </div>
      )}

      {phase === "previewing" && (
        <div className="rounded-lg border bg-white p-6">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Loader2 className="h-4 w-4 animate-spin text-slate-500" aria-hidden />
            <span>Screening ~500 tickers… this typically takes 15–30 seconds (free).</span>
          </div>
        </div>
      )}

      {phase === "preview_ready" && preview && (
        <PreviewCard
          preview={preview}
          onCancel={cancel}
          onConfirm={startRun}
          onRefresh={startPreview}
        />
      )}

      {phase === "running" && preview && (
        <RunningCard total={preview.candidates.length} />
      )}

      {phase === "done" && result && (
        <ResultsCard result={result} onReset={cancel} />
      )}
    </main>
  );
}

function PreviewCard({
  preview,
  onCancel,
  onConfirm,
  onRefresh,
}: {
  preview: ScreenerPreviewResponse;
  onCancel: () => void;
  onConfirm: () => void;
  onRefresh: () => void;
}) {
  const { candidates, universe_size, filtered_out, estimated_cost_usd, model, overflowed, errors } =
    preview;

  return (
    <div className="rounded-lg border bg-white p-6">
      <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
        Step 2 — Confirm paid analysis
      </h2>
      <p className="mt-2 text-sm text-slate-700">
        Found <span className="font-semibold">{candidates.length}</span> candidate
        {candidates.length === 1 ? "" : "s"} out of {universe_size} (
        {filtered_out} filtered out). Estimated cost:{" "}
        <span className="font-semibold">${estimated_cost_usd.toFixed(2)}</span> with{" "}
        <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">{model}</code>.
      </p>
      {overflowed && (
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          More than 30 candidates passed — list trimmed to the strongest 30 (lowest RSI first)
          to keep cost predictable.
        </p>
      )}
      {errors.length > 0 && (
        <details className="mt-2 text-xs text-slate-500">
          <summary className="cursor-pointer">
            {errors.length} non-fatal warning{errors.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-1 list-disc pl-5">
            {errors.slice(0, 10).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </details>
      )}

      <CandidatesTable rows={candidates} />

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={onConfirm}
          disabled={candidates.length === 0}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Run Claude analysis (~${estimated_cost_usd.toFixed(2)})
        </button>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-md border bg-white px-4 py-2 text-sm hover:bg-slate-50"
        >
          Re-run screen
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-sm text-slate-600 hover:underline"
        >
          Cancel
        </button>
      </div>
      <p className="mt-3 text-xs text-slate-400">
        Same-day re-analysis hits the verdict cache and costs $0.
      </p>
    </div>
  );
}

function CandidatesTable({ rows }: { rows: ScreenerCandidate[] }) {
  if (rows.length === 0) {
    return (
      <p className="mt-4 rounded-md border bg-slate-50 p-4 text-sm text-slate-600">
        No candidates passed the strict filter today. Try again after the close — the
        market may simply not be offering setups right now.
      </p>
    );
  }
  return (
    <div className="mt-4 overflow-x-auto rounded-md border">
      <table className="min-w-full divide-y text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 text-left">Ticker</th>
            <th className="px-3 py-2 text-left">Sector</th>
            <th className="px-3 py-2 text-right">Close</th>
            <th className="px-3 py-2 text-right">RSI-14</th>
            <th className="px-3 py-2 text-right">MACD hist</th>
            <th className="px-3 py-2 text-right">SMA-50</th>
            <th className="px-3 py-2 text-right">Vol vs 20d</th>
          </tr>
        </thead>
        <tbody className="divide-y bg-white">
          {rows.map((c) => (
            <tr key={c.symbol}>
              <td className="px-3 py-2 font-mono font-medium">{c.symbol}</td>
              <td className="px-3 py-2 text-slate-600">{c.sector}</td>
              <td className="px-3 py-2 text-right tabular-nums">${c.close.toFixed(2)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{c.rsi_14.toFixed(1)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{c.macd_hist.toFixed(3)}</td>
              <td className="px-3 py-2 text-right tabular-nums">${c.sma_50.toFixed(2)}</td>
              <td className="px-3 py-2 text-right tabular-nums">
                {c.volume_20d_avg > 0
                  ? `${((c.volume_current / c.volume_20d_avg - 1) * 100).toFixed(0)}%`
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunningCard({ total }: { total: number }) {
  return (
    <div className="rounded-lg border bg-white p-6">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin text-slate-500" aria-hidden />
        <span>
          Analyzing {total} ticker{total === 1 ? "" : "s"} sequentially… ~5 seconds each.
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Verdicts that already exist for today (cached) return instantly.
      </p>
    </div>
  );
}

function ResultsCard({
  result,
  onReset,
}: {
  result: ScreenerRunResponse;
  onReset: () => void;
}) {
  const sorted = useMemo(() => {
    const order = { BUY: 0, HOLD: 1, SELL: 2 } as const;
    return [...result.verdicts].sort((a, b) => {
      const oa = order[a.action];
      const ob = order[b.action];
      if (oa !== ob) return oa - ob;
      return b.confidence - a.confidence;
    });
  }, [result.verdicts]);

  const buyCount = sorted.filter((v) => v.action === "BUY").length;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-white p-4">
        <p className="text-sm">
          <span className="font-semibold">{buyCount}</span> BUY verdict
          {buyCount === 1 ? "" : "s"} of {sorted.length} candidate
          {sorted.length === 1 ? "" : "s"} analyzed.{" "}
          <button
            type="button"
            onClick={onReset}
            className="text-xs text-slate-600 hover:underline"
          >
            Run a new scan
          </button>
        </p>
        {result.errors.length > 0 && (
          <details className="mt-2 text-xs text-slate-500">
            <summary className="cursor-pointer">
              {result.errors.length} analysis error{result.errors.length === 1 ? "" : "s"}
            </summary>
            <ul className="mt-1 list-disc pl-5">
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </details>
        )}
      </div>

      <ul className="divide-y rounded-lg border bg-white">
        {sorted.map((v) => (
          <li key={v.id}>
            <Link
              href={`/ticker/${v.ticker}?v=${v.id}`}
              className="flex items-center justify-between gap-4 p-3 text-sm hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <span
                  className={
                    "inline-block w-14 rounded px-2 py-0.5 text-center text-xs font-semibold " +
                    (v.action === "BUY"
                      ? "bg-emerald-100 text-emerald-800"
                      : v.action === "SELL"
                        ? "bg-rose-100 text-rose-800"
                        : "bg-slate-100 text-slate-700")
                  }
                >
                  {v.action}
                </span>
                <span className="font-mono font-medium">{v.ticker}</span>
                <span className="text-slate-600">{v.headline}</span>
              </div>
              <span className="shrink-0 text-xs text-slate-500">{v.confidence}%</span>
            </Link>
          </li>
        ))}
      </ul>

      <p className="text-xs text-slate-400">Not financial advice.</p>
    </div>
  );
}
