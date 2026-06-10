"""Screener: ranking, constituents parsing, manual universe parsing.
Pure parts only — the network paths (constituents CSV, price fetches) are
exercised by the CLI smoke run, not unit tests."""

from bull_api import screen
from bull_api.strategy.base import StrategyDecision


def decision(action: str, confidence: int = 65, strategy: str = "turtle-20-v1") -> StrategyDecision:
    return StrategyDecision(
        strategy=strategy,
        candidate_action=action,
        base_confidence=confidence,
        reason="test" if action == "BUY" else "no setup: donchian_20_breakout",
        filters={},
        setup={},
        entry=100.0 if action == "BUY" else None,
        stop=96.0 if action == "BUY" else None,
        target=108.0 if action == "BUY" else None,
        reward_risk=2.0 if action == "BUY" else None,
    )


def row(ticker: str, action: str, confidence: int = 65) -> dict:
    return {
        "ticker": ticker,
        "active": decision(action, confidence),
        "others": {"pullback-v1": "HOLD"},
    }


def test_rank_results_splits_and_sorts():
    rows = [
        row("AAA", "HOLD"),
        row("BBB", "BUY", 65),
        row("CCC", "BUY", 75),
        row("DDD", "BUY", 65),
    ]
    out = screen.rank_results(rows)
    assert [c["ticker"] for c in out["candidates"]] == ["CCC", "BBB", "DDD"]
    assert out["candidates"][0]["entry"] == 100.0
    assert out["candidates"][0]["other_strategies"] == {"pullback-v1": "HOLD"}
    assert [h["ticker"] for h in out["holds"]] == ["AAA"]
    assert "no setup" in out["holds"][0]["reason"]


def test_rank_results_empty():
    out = screen.rank_results([])
    assert out == {"candidates": [], "holds": []}


def test_parse_constituents_normalizes_and_maps():
    csv_text = (
        "Symbol,Security,GICS Sector,GICS Sub-Industry\n"
        "MMM,3M,Industrials,Industrial Conglomerates\n"
        "BRK.B,Berkshire Hathaway,Financials,Multi-Sector Holdings\n"
        "NVDA,Nvidia,Information Technology,Semiconductors\n"
    )
    rows = screen._parse_constituents(csv_text)
    assert [r["symbol"] for r in rows] == ["MMM", "BRK-B", "NVDA"]  # yfinance dash fix
    # GICS taxonomy translated to the yfinance taxonomy market_context keys on
    assert rows[1]["sector"] == "Financial Services"
    assert rows[2]["sector"] == "Technology"
    assert rows[2]["industry"] == "Semiconductors"  # keyword-matches SOXX downstream


def test_gics_map_covers_all_eleven_sectors():
    assert len(screen.GICS_TO_YF_SECTOR) == 11


def test_fetch_universe_manual_override(monkeypatch):
    monkeypatch.setattr(screen.settings, "bull_screen_universe", "cat, hd ,JPM")
    universe = screen.fetch_universe(size=50)
    assert [u["symbol"] for u in universe] == ["CAT", "HD", "JPM"]
    assert all(u["sector"] is None for u in universe)  # resolved via fundamentals later
