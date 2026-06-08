"""Phase 2 — calibration & edge analysis of scored verdicts.

Answers the prerequisite questions for any gating (Phase 3): *is confidence even
meaningful?* and *which setup features actually carry realized edge?* Mirrors
`scoring.summary()` but slices outcomes by the bucketed `Context`
(`policy/features.py`) instead of just `(action, horizon)`. Reuses scoring's
`_classify_hit` / `_hit_stats` / `_ret_stats` so the win/loss threshold stays a
runtime knob, not a schema field.

≈free: pure aggregation over the existing `VerdictScore` + `Verdict` tables — no
LLM, no migration. Signal only emerges once enough verdicts are scored
(`python -m bull_api.scoring`); thin buckets are flagged via `thin: true` rather
than dropped, so the caller can see *why* a table is empty.

Layering: the table builders are pure functions over a list of `Outcome`s
(hand-testable with synthetic rows); `collect_outcomes` / `report` add the DB.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SessionLocal
from ..models import Verdict, VerdictScore
from ..scoring import _classify_hit, _hit_stats, _ret_stats
from .features import Context, context_for

logger = logging.getLogger(__name__)

# Confidence bands in descending order, for stable calibration-table layout.
_CONF_ORDER = ["85-100", "70-84", "55-69", "40-54", "0-39", "none"]

# Context features the edge table slices on (one marginal table each). The full
# 9-D bucket_key is far too sparse for a few hundred verdicts; per-feature
# marginals stay populated and answer "does this dimension carry edge?".
EDGE_FEATURES: tuple[str, ...] = (
    "confidence_band",
    "reward_risk_band",
    "trend_aligned",
    "sector_above_sma_50",
    "market_above_sma_50",
    "vix_state",
    "earnings_window",
)

# Default minimum sample size before a bucket's stats are trusted.
DEFAULT_MIN_N = 5


@dataclass(frozen=True)
class Outcome:
    """One scored verdict at one horizon: its setup context + realized return."""

    context: Context
    action: str
    horizon_days: int
    return_pct: float


def _bucket_value(v: Any) -> str:
    """Stringify a feature value for use as a JSON object key."""
    if v is None:
        return "none"
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v)


def _stats(hits: list[bool], rets: list[float], min_n: int) -> dict[str, Any]:
    """Combine hit-rate and return stats; flag buckets below `min_n` as thin."""
    out: dict[str, Any] = {**_hit_stats(hits), **_ret_stats(rets)}
    if out["n"] < min_n:
        out["thin"] = True
    return out


def calibration_table(
    outcomes: list[Outcome], *, threshold: float = 0.0, min_n: int = DEFAULT_MIN_N
) -> dict[str, Any]:
    """Per horizon, hit-rate + return stats bucketed by confidence band.

    Pure. The diagonal that says whether higher stated confidence actually maps
    to a higher realized hit rate.
    """
    hits: dict[tuple[int, str], list[bool]] = defaultdict(list)
    rets: dict[tuple[int, str], list[float]] = defaultdict(list)

    for o in outcomes:
        hit = _classify_hit(o.action, o.return_pct, threshold)
        if hit is None:
            continue
        band = _bucket_value(o.context.confidence_band)
        key = (o.horizon_days, band)
        hits[key].append(hit)
        rets[key].append(o.return_pct)

    horizons = sorted({h for h, _ in hits})
    table: dict[str, Any] = {}
    for h in horizons:
        bands = {b for hh, b in hits if hh == h}
        ordered = [b for b in _CONF_ORDER if b in bands]
        table[f"{h}d"] = {
            b: _stats(hits[(h, b)], rets[(h, b)], min_n) for b in ordered
        }
    return table


def edge_table(
    outcomes: list[Outcome], *, threshold: float = 0.0, min_n: int = DEFAULT_MIN_N
) -> dict[str, Any]:
    """Per horizon, per context feature, hit-rate + return stats per value.

    Pure. One marginal table per feature in `EDGE_FEATURES`; thin buckets are
    flagged, not dropped.
    """
    # (horizon, feature, value) -> hits / rets
    hits: dict[tuple[int, str, str], list[bool]] = defaultdict(list)
    rets: dict[tuple[int, str, str], list[float]] = defaultdict(list)

    for o in outcomes:
        hit = _classify_hit(o.action, o.return_pct, threshold)
        if hit is None:
            continue
        for feat in EDGE_FEATURES:
            val = _bucket_value(getattr(o.context, feat))
            key = (o.horizon_days, feat, val)
            hits[key].append(hit)
            rets[key].append(o.return_pct)

    horizons = sorted({h for h, _, _ in hits})
    table: dict[str, Any] = {}
    for h in horizons:
        feat_block: dict[str, Any] = {}
        for feat in EDGE_FEATURES:
            values = sorted({v for hh, f, v in hits if hh == h and f == feat})
            if not values:
                continue
            feat_block[feat] = {
                v: _stats(hits[(h, feat, v)], rets[(h, feat, v)], min_n)
                for v in values
            }
        table[f"{h}d"] = feat_block
    return table


async def collect_outcomes(session: AsyncSession) -> list[Outcome]:
    """Join scores to verdicts and attach each verdict's bucketed context.

    Context is derived once per verdict and shared across that verdict's
    horizons (a verdict has up to len(DEFAULT_HORIZONS) score rows).
    """
    stmt = select(VerdictScore, Verdict).join(Verdict, VerdictScore.verdict_id == Verdict.id)
    rows = list((await session.execute(stmt)).all())

    ctx_cache: dict[int, Context] = {}
    outcomes: list[Outcome] = []
    for score, verdict in rows:
        ctx = ctx_cache.get(verdict.id)
        if ctx is None:
            ctx = context_for(verdict)
            ctx_cache[verdict.id] = ctx
        outcomes.append(
            Outcome(
                context=ctx,
                action=verdict.action,
                horizon_days=score.horizon_days,
                return_pct=score.realized_return_pct,
            )
        )
    return outcomes


async def report(
    session: AsyncSession, *, threshold: float = 0.0, min_n: int = DEFAULT_MIN_N
) -> dict[str, Any]:
    """Full Phase-2 surface: calibration + edge over all scored verdicts."""
    outcomes = await collect_outcomes(session)
    return {
        "threshold_pct": threshold,
        "min_n": min_n,
        "scored_rows": len(outcomes),
        "calibration": calibration_table(outcomes, threshold=threshold, min_n=min_n),
        "edge": edge_table(outcomes, threshold=threshold, min_n=min_n),
    }


def _print_block(title: str, block: dict[str, Any]) -> None:
    print(f"\n{title}")
    for horizon, body in block.items():
        print(f"  [{horizon}]")
        _print_buckets(body, indent=4)


def _print_buckets(body: dict[str, Any], indent: int) -> None:
    pad = " " * indent
    for key, val in body.items():
        if "n" in val:  # leaf: a stats dict
            thin = "  THIN" if val.get("thin") else ""
            print(
                f"{pad}{key:>10s}  n={val['n']:>3d}  hit={val['hit_rate']!s:>6s}"
                f"  mean={val['mean_return_pct']!s:>8s}%  median={val['median_return_pct']!s:>8s}%{thin}"
            )
        else:  # nested feature block
            print(f"{pad}{key}:")
            _print_buckets(val, indent + 4)


async def _cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    async with SessionLocal() as session:
        r = await report(session)
    print(
        f"scored_rows={r['scored_rows']}  threshold={r['threshold_pct']}%  min_n={r['min_n']}"
    )
    if not r["scored_rows"]:
        print("\nNo scored verdicts yet — run `python -m bull_api.scoring` first.")
        return
    _print_block("CALIBRATION (hit rate by confidence band)", r["calibration"])
    _print_block("EDGE (hit rate by context feature)", r["edge"])


if __name__ == "__main__":
    asyncio.run(_cli())
