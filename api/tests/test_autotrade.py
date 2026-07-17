"""Autotrade daily loop: candidate selection, gate-respecting placement, dry-run.

The network/broker boundaries (screen, facts fetch, Alpaca) are monkeypatched; the
DB is a real in-memory SQLite session so verdict/decision/order persistence and the
`algo_json` shape `/orders` reads are exercised for real.
"""

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bull_api import autotrade
from bull_api.db import Base
from bull_api.models import SHADOW_MODEL, Order, PolicyDecision, Verdict
from bull_api.policy.gate import PolicyDecision as GateDecision
from bull_api.repos import verdicts as vrepo
from bull_api.routers import verdict_to_response
from bull_api.strategy.base import StrategyDecision
from bull_api.time import now_utc, trading_day


@pytest_asyncio.fixture
async def session():
    # StaticPool + a single shared connection so create_all and the session see
    # the same in-memory DB.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


def make_decision(action: str = "BUY", strategy: str = "turtle-20-v1") -> StrategyDecision:
    if action == "BUY":
        return StrategyDecision(
            strategy=strategy,
            candidate_action="BUY",
            base_confidence=65,
            reason="donchian_20_breakout",
            filters={},
            setup={},
            entry=100.0,
            stop=96.0,
            target=108.0,
            reward_risk=2.0,
        )
    return StrategyDecision(
        strategy=strategy,
        candidate_action="HOLD",
        base_confidence=60,
        reason="no setup",
        filters={},
        setup={},
    )


def make_facts(date_str: str) -> dict:
    return {
        "ticker": "AAA",
        "support_resistance": {"support": [{"price": 96.0}], "resistance": [{"price": 108.0}]},
        "prices": [
            {"date": date_str, "open": 99.0, "high": 101.0, "low": 98.0,
             "close": 100.0, "volume": 1000}
        ],
    }


def gate(act: bool, size_pct: float = 2.0) -> GateDecision:
    return GateDecision(act=act, size_pct=size_pct, rationale="test")


def patch_common(monkeypatch, *, decision, facts, gate_decision, positions, tickers=("AAA",)):
    monkeypatch.setattr(
        autotrade, "run_screen", lambda *a, **k: {"candidates": [{"ticker": t} for t in tickers]}
    )
    monkeypatch.setattr(autotrade, "build_screen_facts", lambda ticker, *a, **k: facts)
    monkeypatch.setattr(autotrade, "REGISTRY", {"turtle-20-v1": lambda f: decision})
    monkeypatch.setattr(autotrade, "decision_for_verdict", lambda v, o: gate_decision)

    async def _outcomes(sess, **k):
        return []

    async def _sweep(sess):
        return {"closed": []}

    async def _score(sess):
        return {"scores_inserted": 0}

    monkeypatch.setattr(autotrade, "collect_outcomes", _outcomes)
    monkeypatch.setattr(autotrade, "sweep", _sweep)
    monkeypatch.setattr(autotrade, "score_pending_verdicts", _score)
    monkeypatch.setattr(
        "bull_api.broker.alpaca.get_account",
        lambda: {"equity": 100000.0, "cash": 100000.0, "buying_power": 100000.0},
    )
    monkeypatch.setattr("bull_api.broker.alpaca.get_positions", lambda: positions)


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar()


async def test_dry_run_no_writes_no_orders(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("BUY"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
    )

    async def _boom(sess):
        raise AssertionError("sweep/score must not run in dry_run")

    monkeypatch.setattr(autotrade, "sweep", _boom)
    monkeypatch.setattr(autotrade, "score_pending_verdicts", _boom)
    monkeypatch.setattr(
        "bull_api.broker.alpaca.place_bracket_order",
        lambda *a, **k: pytest.fail("no order in dry_run"),
    )

    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=True)

    assert summary["placed"] and summary["placed"][0]["dry_run"] is True
    assert await _count(session, Verdict) == 0
    assert await _count(session, Order) == 0
    assert await _count(session, PolicyDecision) == 0


async def test_max_new_truncates_candidates(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("BUY"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
        tickers=("AAA", "BBB", "CCC", "DDD", "EEE"),
    )
    summary = await autotrade.run_autotrade(session, max_new=2, dry_run=True)
    assert summary["candidates"] == 2


async def test_already_held_skipped(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("BUY"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[{"symbol": "AAA"}],
    )
    monkeypatch.setattr(
        "bull_api.broker.alpaca.place_bracket_order",
        lambda *a, **k: pytest.fail("held ticker must not be re-bought"),
    )
    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)
    assert summary["skipped"] == [{"ticker": "AAA", "reason": "already_held"}]
    assert await _count(session, Order) == 0
    assert await _count(session, Verdict) == 0


async def test_stale_session_skipped(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("BUY"),
        facts=make_facts("2000-01-03"),  # not today
        gate_decision=gate(True),
        positions=[],
    )
    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)
    assert summary["skipped"][0]["reason"] == "stale_session"
    assert await _count(session, Verdict) == 0


async def test_reevaluated_hold_skipped(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("HOLD"),  # re-eval flips the screen BUY to HOLD
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
    )
    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)
    assert summary["skipped"][0]["reason"] == "reevaluated_HOLD"
    assert await _count(session, Verdict) == 0


async def test_gate_decline_skips_but_records_decision(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("BUY"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(False, size_pct=0.0),  # gate declines
        positions=[],
    )
    monkeypatch.setattr(
        "bull_api.broker.alpaca.place_bracket_order",
        lambda *a, **k: pytest.fail("declined trade must not place an order"),
    )
    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)

    assert summary["skipped"][0]["reason"] == "gate_declined"
    assert summary["placed"] == []
    # Verdict minted + decision recorded for forward-testing; no order placed.
    assert await _count(session, Verdict) == 1
    assert await _count(session, PolicyDecision) == 1
    assert await _count(session, Order) == 0


async def test_happy_path_places_bracket_with_strategy_levels(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("BUY"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True, size_pct=2.0),
        positions=[],
    )
    calls: dict = {}

    def fake_bracket(symbol, qty, stop_price, target_price):
        calls.update(symbol=symbol, qty=qty, stop=stop_price, target=target_price)
        return {
            "alpaca_order_id": "abc123",
            "symbol": symbol,
            "qty": qty,
            "status": "accepted",
            "submitted_at": None,
            "filled_avg_price": None,
            "legs": {"stop_loss": "sl1", "take_profit": "tp1"},
        }

    monkeypatch.setattr("bull_api.broker.alpaca.place_bracket_order", fake_bracket)

    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)

    # Bracket placed with the strategy's own stop/target.
    assert calls["stop"] == 96.0 and calls["target"] == 108.0
    assert calls["qty"] == 20  # $2000 notional // $100 close
    assert len(summary["placed"]) == 1

    order = (await session.execute(select(Order))).scalars().one()
    assert order.order_class == "bracket"
    assert order.stop_price == 96.0 and order.target_price == 108.0

    verdict = (await session.execute(select(Verdict))).scalars().one()
    assert verdict.action == "BUY"
    assert verdict.model_used == "algo"
    assert verdict.algo_json["active_strategy"] == "turtle-20-v1"
    ev = verdict.algo_json["evaluations"]["turtle-20-v1"]
    assert ev["stop"] == 96.0 and ev["target"] == 108.0
    assert verdict.algo_json["llm_review"] is None


def patch_shadow(monkeypatch, *, shadow_candidates, shadow_decision, facts):
    """On top of patch_common: no active candidates, a pullback shadow feed."""
    monkeypatch.setattr(
        autotrade,
        "run_screen",
        lambda *a, **k: {"candidates": [], "shadow_candidates": shadow_candidates},
    )
    monkeypatch.setattr(
        autotrade,
        "REGISTRY",
        {
            "turtle-20-v1": lambda f: make_decision("HOLD"),
            "pullback-v1": lambda f: shadow_decision,
        },
    )
    monkeypatch.setattr(autotrade, "build_screen_facts", lambda ticker, *a, **k: facts)


async def test_shadow_verdict_minted_score_only(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("HOLD"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
    )
    patch_shadow(
        monkeypatch,
        shadow_candidates=[{"ticker": "AAA", "strategy": "pullback-v1"}],
        shadow_decision=make_decision("BUY", strategy="pullback-v1"),
        facts=make_facts(trading_day().isoformat()),
    )

    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)

    assert [(s["ticker"], s["strategy"]) for s in summary["shadow"]] == [("AAA", "pullback-v1")]
    verdict = (await session.execute(select(Verdict))).scalars().one()
    assert verdict.model_used == SHADOW_MODEL
    assert verdict.action == "BUY"
    assert verdict.algo_json["active_strategy"] == "pullback-v1"
    # Score-only: no gate decision, no order.
    assert await _count(session, PolicyDecision) == 0
    assert await _count(session, Order) == 0
    # Shadow rows never satisfy the /analyze cache, watchlist, or listings…
    assert await vrepo.get_for_today("AAA", trading_day(), session) is None
    assert await vrepo.latest_for("AAA", session, timeframe="short") is None
    assert await vrepo.list_recent(10, session) == []
    # …but are reachable when explicitly asked for.
    assert len(await vrepo.list_recent(10, session, include_shadow=True)) == 1


async def test_shadow_rerun_same_day_is_idempotent(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("HOLD"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
    )
    patch_shadow(
        monkeypatch,
        shadow_candidates=[{"ticker": "AAA", "strategy": "pullback-v1"}],
        shadow_decision=make_decision("BUY", strategy="pullback-v1"),
        facts=make_facts(trading_day().isoformat()),
    )

    await autotrade.run_autotrade(session, max_new=3, dry_run=False)
    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)

    assert summary["shadow"] == []
    assert await _count(session, Verdict) == 1


async def test_shadow_reeval_hold_not_minted(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("HOLD"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
    )
    patch_shadow(
        monkeypatch,
        shadow_candidates=[{"ticker": "AAA", "strategy": "pullback-v1"}],
        shadow_decision=make_decision("HOLD", strategy="pullback-v1"),  # re-eval flips it
        facts=make_facts(trading_day().isoformat()),
    )

    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)
    assert summary["shadow"] == []
    assert await _count(session, Verdict) == 0


async def test_shadow_dry_run_no_writes(session, monkeypatch):
    patch_common(
        monkeypatch,
        decision=make_decision("HOLD"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
    )
    patch_shadow(
        monkeypatch,
        shadow_candidates=[{"ticker": "AAA", "strategy": "pullback-v1"}],
        shadow_decision=make_decision("BUY", strategy="pullback-v1"),
        facts=make_facts(trading_day().isoformat()),
    )

    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=True)

    assert summary["shadow"] == [{"ticker": "AAA", "strategy": "pullback-v1", "dry_run": True}]
    assert await _count(session, Verdict) == 0


async def test_shadow_daily_cap(session, monkeypatch):
    tickers = [f"T{i:02d}" for i in range(autotrade.MAX_SHADOW_PER_DAY + 2)]
    patch_common(
        monkeypatch,
        decision=make_decision("HOLD"),
        facts=make_facts(trading_day().isoformat()),
        gate_decision=gate(True),
        positions=[],
    )
    patch_shadow(
        monkeypatch,
        shadow_candidates=[{"ticker": t, "strategy": "pullback-v1"} for t in tickers],
        shadow_decision=make_decision("BUY", strategy="pullback-v1"),
        facts=make_facts(trading_day().isoformat()),
    )

    summary = await autotrade.run_autotrade(session, max_new=3, dry_run=False)
    assert len(summary["shadow"]) == autotrade.MAX_SHADOW_PER_DAY
    assert await _count(session, Verdict) == autotrade.MAX_SHADOW_PER_DAY


def test_minted_verdict_serializes_to_response():
    # Autotrade rows carry a reasoning-only report_json; the listing endpoint
    # must still validate them (regression: one such row 500'd GET /verdicts).
    verdict = autotrade._mint_verdict(
        "AAA", "turtle-20-v1", {"turtle-20-v1": make_decision("BUY")}, make_facts("2026-07-06")
    )
    verdict.id = 1
    verdict.created_at = now_utc()

    resp = verdict_to_response(verdict)
    assert resp.report.reasoning
    assert resp.report.technical == ""
    assert resp.report.risks == ""
