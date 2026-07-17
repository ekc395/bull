"""Unattended daily algo loop: sweep → score → screen → gate → auto-place brackets.

Zero API cost. In short mode the deterministic strategy IS the decision; the Opus
veto/shade is dropped here, so no Anthropic client is ever constructed. Each top
candidate from the free screener is minted straight into a Verdict from the active
strategy's `StrategyDecision` (`model_used="algo"`), sized through the *same* policy
gate a manual click uses, and executed as the *same* bracket order (entry + GTC
stop/target legs Alpaca runs server-side).

One deliberate difference from the manual `/orders` click: a manual click overrides
a gate decline up to base size (the policy never blocks a human). Automation must NOT
do that — an unattended loop respects the decline and skips. The gate's decision is
still recorded either way, so it stays forward-testable.

Sweep + scoring run first so exits/outcomes are current before new capital is sized.

Run: cd api && python -m bull_api.autotrade [--dry-run] [--max-new N]
Scheduled via .github/workflows/autotrade.yml (daily, after the US close). Standalone
process — talks straight to the DB + Alpaca, no FastAPI server required.
"""

import argparse
import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .broker import alpaca
from .config import settings
from .db import SessionLocal
from .models import SHADOW_MODEL, Verdict
from .policy.analysis import collect_outcomes
from .policy.gate import decision_for_verdict
from .repos import policy as prepo
from .repos import verdicts as vrepo
from .routers.broker import place_order, sweep
from .schemas import ExecuteOrderRequest
from .scoring import score_pending_verdicts
from .screen import build_screen_facts, run_screen
from .strategy import REGISTRY
from .time import trading_day

logger = logging.getLogger(__name__)

# Daily cap on score-only shadow verdicts (plan.md → Shadow verdict scoring):
# bounds the nightly scoring loop's per-verdict price fetches, nothing else.
MAX_SHADOW_PER_DAY = 10


def _mint_verdict(
    ticker: str,
    active_name: str,
    decisions: dict[str, Any],
    facts: dict[str, Any],
    *,
    model: str = "algo",
) -> Verdict:
    """A deterministic Verdict from the strategy layer — no LLM. Mirrors the
    Verdict constructed at the end of `agent.analyze_ticker` (same columns and
    `algo_json` shape `/orders` reads for the bracket legs), minus the review."""
    active = decisions[active_name]
    return Verdict(
        ticker=ticker,
        action=active.candidate_action,
        confidence=active.base_confidence,
        headline=f"{active.strategy}: {active.reason}"[:280],
        report_json={"reasoning": f"Deterministic {active.strategy} entry — no LLM veto/shade."},
        key_levels_json=facts["support_resistance"],
        # created_at auto-fills via the model's now_utc default.
        timeframe="short",
        # Sentinel model tag ("algo", or SHADOW_MODEL for score-only shadows):
        # keeps no-LLM rows separable in scoring's by_model breakdown; outcomes
        # still pool across models for the gate.
        model_used=model,
        candidate_action=active.candidate_action,
        candidate_confidence=active.base_confidence,
        algo_json={
            "active_strategy": active_name,
            "evaluations": {name: d.to_json() for name, d in decisions.items()},
            "llm_review": None,
        },
        raw_response_json={"source": "autotrade"},
        facts_bundle_json=facts,
    )


async def _mint_shadow_verdicts(
    session: AsyncSession, report: dict[str, Any], *, dry_run: bool
) -> list[dict[str, Any]]:
    """Persist score-only verdicts for non-active-strategy BUYs (plan.md →
    Shadow verdict scoring). No gate, no policy_decisions row, no order — the
    rows exist purely so `score_pending_verdicts` accumulates an unbiased live
    track record per strategy. Idempotent per (ticker, strategy, trading day).
    """
    shadow_cands = report.get("shadow_candidates", [])[:MAX_SHADOW_PER_DAY]
    if not shadow_cands:
        return []

    today = trading_day()
    seen: set[tuple[str, str | None]] = set()
    if not dry_run:
        existing = await vrepo.list_for_day(today, session, model_used=SHADOW_MODEL)
        seen = {(v.ticker, (v.algo_json or {}).get("active_strategy")) for v in existing}

    minted: list[dict[str, Any]] = []
    facts_cache: dict[str, dict[str, Any]] = {}  # overlap: two strategies, one ticker
    for c in shadow_cands:
        ticker, strat = c["ticker"], c["strategy"]
        if (ticker, strat) in seen:
            continue
        facts = facts_cache.get(ticker)
        if facts is None:
            try:
                facts = facts_cache[ticker] = build_screen_facts(ticker)
            except Exception as e:
                logger.warning("autotrade: shadow facts fetch failed for %s: %s", ticker, e)
                continue
        prices = facts.get("prices") or []
        if not prices or prices[-1]["date"] != today.isoformat():
            continue  # weekend/holiday: same stale-session rule as the active path
        decisions = {name: fn(facts) for name, fn in REGISTRY.items()}
        decision = decisions.get(strat)
        if decision is None or decision.candidate_action != "BUY":
            continue  # re-eval with the real earnings date flipped it, or strategy retired
        if dry_run:
            logger.info("autotrade[dry-run]: shadow %s %s", strat, ticker)
            minted.append({"ticker": ticker, "strategy": strat, "dry_run": True})
            continue
        verdict = await vrepo.insert(
            _mint_verdict(ticker, strat, decisions, facts, model=SHADOW_MODEL), session
        )
        seen.add((ticker, strat))
        minted.append({"ticker": ticker, "strategy": strat, "verdict_id": verdict.id})
        logger.info("autotrade: shadow verdict %s %s (verdict %d)", strat, ticker, verdict.id)
    return minted


async def run_autotrade(
    session: AsyncSession, *, max_new: int, dry_run: bool = False
) -> dict[str, Any]:
    """The daily loop. Returns a summary dict (swept/scored/candidates/placed/skipped).

    dry_run: screen + gate + log intended orders only — no sweep, no scoring, no DB
    writes, no Alpaca orders (read-only account/position lookups still happen).
    """
    summary: dict[str, Any] = {
        "dry_run": dry_run,
        "swept": None,
        "scored": None,
        "candidates": 0,
        "placed": [],
        "skipped": [],
        "shadow": [],
    }

    if not dry_run:
        summary["swept"] = await sweep(session)
        summary["scored"] = await score_pending_verdicts(session)

    report = run_screen()
    # Shadow verdicts first: they need no Alpaca account and must run even on
    # days the active strategy is flat.
    summary["shadow"] = await _mint_shadow_verdicts(session, report, dry_run=dry_run)
    candidates = report.get("candidates", [])[:max_new]
    summary["candidates"] = len(candidates)
    if not candidates:
        logger.info("autotrade: no setups today — strategy is flat by design most days")
        return summary

    try:
        account = alpaca.get_account()
        positions = alpaca.get_positions()
    except RuntimeError as e:
        logger.error("autotrade: Alpaca unavailable (%s) — skipping placement", e)
        summary["error"] = str(e)
        return summary

    held = {p["symbol"] for p in positions}
    equity = float(account["equity"])
    today = trading_day().isoformat()
    outcomes = await collect_outcomes(session)

    def skip(ticker: str, reason: str, **extra: Any) -> None:
        summary["skipped"].append({"ticker": ticker, "reason": reason, **extra})

    for c in candidates:
        ticker = c["ticker"]
        if ticker in held:
            skip(ticker, "already_held")  # no pyramiding; idempotent across re-runs
            continue

        try:
            facts = build_screen_facts(ticker)  # no sector arg → real earnings date
        except Exception as e:
            logger.warning("autotrade: facts fetch failed for %s: %s", ticker, e)
            skip(ticker, "facts_error", detail=str(e))
            continue

        prices = facts.get("prices") or []
        if not prices or prices[-1]["date"] != today:
            skip(ticker, "stale_session")  # weekend/holiday: don't trade last close again
            continue

        decisions = {name: fn(facts) for name, fn in REGISTRY.items()}
        active_name = (
            settings.bull_active_strategy
            if settings.bull_active_strategy in decisions
            else next(iter(decisions))
        )
        decision = decisions[active_name]
        if decision.candidate_action != "BUY":
            # Re-eval with the real earnings date can flip a screen BUY to HOLD.
            skip(ticker, f"reevaluated_{decision.candidate_action}")
            continue

        verdict = _mint_verdict(ticker, active_name, decisions, facts)
        gate = decision_for_verdict(verdict, outcomes)
        last_close = float(prices[-1]["close"])
        notional = round(equity * gate.size_pct / 100, 2) if gate.act else 0.0

        if dry_run:
            shares = int(notional // last_close) if last_close else 0
            logger.info(
                "autotrade[dry-run]: %s act=%s size=%.2f%% notional=$%.2f ~%dsh "
                "stop=%.2f target=%.2f (%s)",
                ticker, gate.act, gate.size_pct, notional, shares,
                decision.stop, decision.target, gate.rationale,
            )
            if gate.act and notional > 0:
                summary["placed"].append(
                    {"ticker": ticker, "notional": notional, "shares": shares, "dry_run": True}
                )
            else:
                skip(ticker, "gate_declined", rationale=gate.rationale)
            continue

        verdict = await vrepo.insert(verdict, session)
        await prepo.insert_decision(gate, verdict.id, session)  # record either way
        if not gate.act or gate.size_pct <= 0:
            skip(ticker, "gate_declined", rationale=gate.rationale)
            continue

        try:
            order = await place_order(
                ExecuteOrderRequest(verdict_id=verdict.id, notional=notional), session
            )
        except Exception as e:
            # e.g. size < 1 whole share (bracket orders reject fractionals).
            logger.error("autotrade: order failed for %s: %s", ticker, e)
            skip(ticker, "order_error", detail=str(e))
            continue

        logger.info("autotrade: placed %s $%.2f (order %s)", ticker, notional, order.id)
        summary["placed"].append({"ticker": ticker, "order_id": order.id, "notional": notional})
        held.add(ticker)

    logger.info(
        "autotrade: candidates=%d placed=%d skipped=%d shadow=%d dry_run=%s",
        summary["candidates"], len(summary["placed"]), len(summary["skipped"]),
        len(summary["shadow"]), dry_run,
    )
    return summary


async def _cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # httpx logs full request URLs at INFO — Finnhub/Alpha Vantage put the API
    # key in the query string, and Actions logs are public on a public repo.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="screen + gate + log only; no writes/orders"
    )
    parser.add_argument(
        "--max-new", type=int, default=settings.bull_autotrade_max_new,
        help="max new positions to open this run",
    )
    args = parser.parse_args()

    async with SessionLocal() as session:
        summary = await run_autotrade(session, max_new=args.max_new, dry_run=args.dry_run)

    tag = "(dry-run) " if args.dry_run else ""
    print(
        f"\nAUTOTRADE {tag}candidates={summary['candidates']} "
        f"placed={len(summary['placed'])} skipped={len(summary['skipped'])}"
    )
    if summary.get("error"):
        print(f"  ERROR: {summary['error']}")
    for p in summary["placed"]:
        print(f"  PLACED {p['ticker']:6s} ${p['notional']:.2f}")
    for s in summary["skipped"]:
        print(f"  skip   {s['ticker']:6s} {s['reason']}")


if __name__ == "__main__":
    asyncio.run(_cli())
