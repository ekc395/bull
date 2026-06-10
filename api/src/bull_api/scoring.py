"""Verdict-vs-realized backtest scoring.

The feedback loop that turns accuracy work from vibes into signal. For each
past Verdict we compute the realized return at fixed trading-day horizons
(default 5 and 20) and persist as VerdictScore rows. Hit-rate aggregation
is dynamic — the win/loss threshold is a runtime knob, not a schema field,
so we can tune it without a migration.

Entry points:
  - score_pending_verdicts(session) — find verdicts past horizon without
    scores; score them
  - summary(session, threshold=...) — aggregate hit rate per (action, horizon)
    plus a per-model breakdown

Scheduling: manual via `python -m bull_api.scoring` or POST /scores/run.
No cron — that's the user's job (launchd / GitHub Actions / etc.).
"""

import asyncio
import logging
from collections import defaultdict
from datetime import date as _date
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import Verdict, VerdictScore
from .time import trading_day
from .tools.prices import get_price_history

logger = logging.getLogger(__name__)

# Trading-day horizons we score. 5d ~ 1 calendar week; 20d ~ 1 calendar month.
DEFAULT_HORIZONS: tuple[int, ...] = (5, 20)


def _find_entry_index(prices_df: pd.DataFrame, verdict_td: _date) -> int | None:
    """Index of the first row whose date is >= the verdict's trading day.

    Handles weekend/holiday verdicts: a Saturday verdict scores from Monday's
    close. Returns None if no such row exists yet.
    """
    matches = prices_df.index[prices_df.index.date >= verdict_td]
    if len(matches) == 0:
        return None
    return int(prices_df.index.get_loc(matches[0]))


async def score_verdict(
    verdict: Verdict,
    session: AsyncSession,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[VerdictScore]:
    """Compute and persist scores for `verdict` at each horizon with enough
    trading data. Skips horizons already scored or not yet elapsed.
    """
    existing_stmt = select(VerdictScore.horizon_days).where(
        VerdictScore.verdict_id == verdict.id
    )
    existing = {row[0] for row in (await session.execute(existing_stmt)).all()}
    needed = [h for h in horizons if h not in existing]
    if not needed:
        return []

    verdict_td = trading_day(verdict.created_at)

    try:
        df = get_price_history(verdict.ticker)
    except Exception as e:
        logger.warning("scoring: prices fetch failed for %s: %s", verdict.ticker, e)
        return []

    entry_idx = _find_entry_index(df, verdict_td)
    if entry_idx is None:
        logger.info(
            "scoring: no entry close for %s on/after %s yet", verdict.ticker, verdict_td
        )
        return []

    entry_close = float(df["Close"].iloc[entry_idx])
    inserted: list[VerdictScore] = []
    for horizon in sorted(needed):
        exit_idx = entry_idx + horizon
        if exit_idx >= len(df):
            continue  # not enough trading days elapsed yet
        exit_close = float(df["Close"].iloc[exit_idx])
        ret_pct = (exit_close / entry_close - 1.0) * 100.0
        score = VerdictScore(
            verdict_id=verdict.id,
            horizon_days=horizon,
            entry_close=round(entry_close, 4),
            exit_close=round(exit_close, 4),
            realized_return_pct=round(ret_pct, 4),
        )
        session.add(score)
        inserted.append(score)

    if inserted:
        await session.commit()
        for s in inserted:
            await session.refresh(s)
    return inserted


async def score_pending_verdicts(
    session: AsyncSession,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, int]:
    """Score every verdict with unfilled horizons. Returns counts.

    Pulls all verdicts and filters in Python — the DB is small and a clean
    SQL anti-join would need a UNION over the static horizons set, not worth
    the cleverness.
    """
    stmt = select(Verdict).order_by(Verdict.created_at)
    verdicts = list((await session.execute(stmt)).scalars().all())

    processed = inserted = 0
    for v in verdicts:
        try:
            new = await score_verdict(v, session, horizons=horizons)
        except Exception:
            logger.exception("scoring failed for verdict %s (%s)", v.id, v.ticker)
            continue
        inserted += len(new)
        processed += 1
    return {"verdicts_processed": processed, "scores_inserted": inserted}


def _classify_hit(action: str, return_pct: float, threshold: float) -> bool | None:
    """BUY/SELL: directional hit. HOLD: within a no-move band (max(threshold, 1.0))."""
    if action == "BUY":
        return return_pct > threshold
    if action == "SELL":
        return return_pct < -threshold
    if action == "HOLD":
        band = max(threshold, 1.0)
        return abs(return_pct) <= band
    return None


def _ret_stats(returns: list[float]) -> dict[str, float | int | None]:
    if not returns:
        return {"n": 0, "mean_return_pct": None, "median_return_pct": None}
    s = sorted(returns)
    mid = len(s) // 2
    median = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
    return {
        "n": len(s),
        "mean_return_pct": round(sum(s) / len(s), 3),
        "median_return_pct": round(median, 3),
    }


def _hit_stats(hits: list[bool]) -> dict[str, float | int | None]:
    return {
        "n": len(hits),
        "hit_rate": round(sum(hits) / len(hits), 4) if hits else None,
    }


async def summary(session: AsyncSession, *, threshold: float = 0.0) -> dict[str, Any]:
    """Hit rate per (action, horizon), per-model breakdown, and — for
    short-mode rows carrying the strategy layer — the forward tournament
    table (`by_strategy`) plus the LLM-overlay comparison (`algo_vs_final`).

    The forward tables are the out-of-sample check on the backtest ranking
    and the ONLY honest measure of the LLM veto/shade layer (which can't be
    backtested — the model knows historical outcomes). Fixed 5/20d horizons:
    a uniform measuring stick, not a per-strategy exit simulation; the
    backtester (`bull_api.backtest`) simulates the actual exits.
    """
    stmt = select(VerdictScore, Verdict).join(Verdict, VerdictScore.verdict_id == Verdict.id)
    rows = list((await session.execute(stmt)).all())

    overall: dict[tuple[str, int], list[bool]] = defaultdict(list)
    by_model: dict[tuple[str, str, int], list[bool]] = defaultdict(list)
    rets: dict[tuple[str, int], list[float]] = defaultdict(list)

    # by_strategy: every registered strategy's candidates graded on the same
    # scored verdicts (candidates were stored per-strategy in algo_json).
    strat_evaluated: dict[tuple[str, int], int] = defaultdict(int)
    strat_buy_hits: dict[tuple[str, int], list[bool]] = defaultdict(list)
    strat_buy_rets: dict[tuple[str, int], list[float]] = defaultdict(list)

    # algo_vs_final: the ACTIVE candidate vs the LLM-reviewed final verdict
    # over the identical row subset, plus veto outcomes.
    cand_hits: dict[tuple[str, int], list[bool]] = defaultdict(list)
    final_hits: dict[tuple[str, int], list[bool]] = defaultdict(list)
    seen_verdicts: set[int] = set()
    agreements = 0
    veto_rets: dict[int, list[float]] = defaultdict(list)

    for score, verdict in rows:
        hit = _classify_hit(verdict.action, score.realized_return_pct, threshold)
        if hit is None:
            continue
        key = (verdict.action, score.horizon_days)
        overall[key].append(hit)
        by_model[(verdict.model_used, *key)].append(hit)
        rets[key].append(score.realized_return_pct)

        algo = verdict.algo_json or {}
        for name, ev in (algo.get("evaluations") or {}).items():
            cand = ev.get("candidate_action")
            skey = (name, score.horizon_days)
            strat_evaluated[skey] += 1
            if cand == "BUY":
                buy_hit = _classify_hit(cand, score.realized_return_pct, threshold)
                if buy_hit is not None:
                    strat_buy_hits[skey].append(buy_hit)
                    strat_buy_rets[skey].append(score.realized_return_pct)

        if verdict.candidate_action:
            c_hit = _classify_hit(
                verdict.candidate_action, score.realized_return_pct, threshold
            )
            if c_hit is not None:
                cand_hits[(verdict.candidate_action, score.horizon_days)].append(c_hit)
            final_hits[key].append(hit)
            if verdict.id not in seen_verdicts:
                seen_verdicts.add(verdict.id)
                if verdict.candidate_action == verdict.action:
                    agreements += 1
            review = algo.get("llm_review") or {}
            if review.get("veto") and verdict.candidate_action == "BUY":
                veto_rets[score.horizon_days].append(score.realized_return_pct)

    return {
        "threshold_pct": threshold,
        "scored_rows": len(rows),
        "by_action_horizon": {
            f"{a}@{h}d": {**_hit_stats(v), **_ret_stats(rets[(a, h)])}
            for (a, h), v in sorted(overall.items())
        },
        "by_model": {
            f"{m}|{a}@{h}d": _hit_stats(v) for (m, a, h), v in sorted(by_model.items())
        },
        "by_strategy": {
            f"{name}@{h}d": {
                "evaluated": strat_evaluated[(name, h)],
                "buys": len(strat_buy_hits[(name, h)]),
                **_hit_stats(strat_buy_hits[(name, h)]),
                **_ret_stats(strat_buy_rets[(name, h)]),
            }
            for (name, h) in sorted(strat_evaluated)
        },
        "algo_vs_final": {
            "candidate": {
                f"{a}@{h}d": _hit_stats(v) for (a, h), v in sorted(cand_hits.items())
            },
            "final": {
                f"{a}@{h}d": _hit_stats(v) for (a, h), v in sorted(final_hits.items())
            },
            "verdicts_compared": len(seen_verdicts),
            "agreement_rate": round(agreements / len(seen_verdicts), 4)
            if seen_verdicts
            else None,
            # Mean realized return of vetoed BUY candidates. Negative ⇒ the
            # LLM's vetoes avoided losses (it is earning its tokens).
            "vetoed_buys": {
                f"{h}d": _ret_stats(v) for h, v in sorted(veto_rets.items())
            },
        },
    }


async def _cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    async with SessionLocal() as session:
        counts = await score_pending_verdicts(session)
        print(
            f"processed={counts['verdicts_processed']} "
            f"inserted={counts['scores_inserted']}"
        )
        s = await summary(session)
        print(f"\nscored_rows={s['scored_rows']}  threshold={s['threshold_pct']}%")
        print("\nBy action x horizon:")
        for k, v in s["by_action_horizon"].items():
            print(
                f"  {k:>14s}  n={v['n']:>3d}  hit={v['hit_rate']!s:>6s}"
                f"  mean={v['mean_return_pct']!s:>8s}%  median={v['median_return_pct']!s:>8s}%"
            )
        if s["by_model"]:
            print("\nBy model:")
            for k, v in s["by_model"].items():
                print(f"  {k:>40s}  n={v['n']:>3d}  hit={v['hit_rate']!s:>6s}")
        if s["by_strategy"]:
            print("\nBy strategy (forward; candidates graded at fixed horizons):")
            for k, v in s["by_strategy"].items():
                print(
                    f"  {k:>18s}  evaluated={v['evaluated']:>3d}  buys={v['buys']:>3d}"
                    f"  hit={v['hit_rate']!s:>6s}  mean={v['mean_return_pct']!s:>8s}%"
                )
        avf = s["algo_vs_final"]
        if avf["verdicts_compared"]:
            print(
                f"\nAlgo vs final: verdicts={avf['verdicts_compared']}"
                f"  agreement={avf['agreement_rate']!s}"
            )
            for label in ("candidate", "final"):
                for k, v in avf[label].items():
                    print(f"  {label:>9s} {k:>9s}  n={v['n']:>3d}  hit={v['hit_rate']!s:>6s}")
            for k, v in avf["vetoed_buys"].items():
                print(
                    f"  vetoed BUYs @{k}: n={v['n']}  mean={v['mean_return_pct']!s}%"
                    "  (negative ⇒ vetoes added value)"
                )


if __name__ == "__main__":
    asyncio.run(_cli())
