"""Free strategy screener: scan the S&P 500 for TODAY's setups.

Inverts the cost model of the watchlist batch. Instead of paying Opus to
analyze a fixed list (mostly HOLDs), this scans the index for free — the
screen criterion IS the registered strategy code — and the paid analysis
happens only on tickers where the active strategy fires.

Two stages:
  1. Universe — current S&P 500 constituents (maintained CSV from the
     `datasets/s-and-p-500-companies` project; fetched once per trading day,
     no HTML scraping, no new deps). Index membership is the quality floor:
     committee-curated size/profitability/liquidity, and the closest live
     distribution to the Dow-30 universe the strategies were validated on.
     `BULL_SCREEN_UNIVERSE` overrides with a manual comma-separated list.
  2. Setup pass — every registered strategy evaluates each ticker's
     point-in-time facts (same live tools: prices/indicators/S&R/market
     context). No LLM, no DB writes.

The CSV carries each name's GICS sector/sub-industry, so the sector regime
filter resolves without the rate-limited fundamentals fetch — a full
503-name scan is just price history (~1-2 min first run; same-day re-runs
hit the per-trading-day caches). Trade-off: earnings dates are NOT known at
screen time, so the earnings-window filter fails open here; the downstream
`/analyze` on any candidate fetches the real date and the policy gate still
refuses to size trades inside the 0-5 day window.

A drifting universe is fine for LIVE scanning — never for backtests.

Run: cd api && python -m bull_api.screen [--size 100] [--tickers AAA,BBB]
"""

import argparse
import csv
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import httpx

from .config import settings
from .strategy import REGISTRY
from .time import trading_day
from .tools.fundamentals import get_fundamentals
from .tools.indicators import compute_indicators
from .tools.market_context import get_market_context
from .tools.prices import get_price_history
from .tools.support_resistance import find_support_resistance

logger = logging.getLogger(__name__)

CONSTITUENTS_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
)
MAX_UNIVERSE_SIZE = 503  # the whole index; CLI/endpoint --size trims for quick runs

PRICE_LOOKBACK_DAYS = 400  # match the live short-mode bundle
PRICE_TAIL_BARS = 60
FETCH_WORKERS = 8

# GICS sector names (the CSV's taxonomy) → yfinance `.info["sector"]` taxonomy,
# which is what tools/market_context.SECTOR_ETF keys on. Sub-industry strings
# pass through unchanged — the keyword matching ("semiconductor" → SOXX, …)
# works on both taxonomies.
GICS_TO_YF_SECTOR: dict[str, str] = {
    "Information Technology": "Technology",
    "Financials": "Financial Services",
    "Health Care": "Healthcare",
    "Consumer Discretionary": "Consumer Cyclical",
    "Consumer Staples": "Consumer Defensive",
    "Materials": "Basic Materials",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Communication Services": "Communication Services",
}

_sp500_cache: dict[date, list[dict[str, Any]]] = {}


def _parse_constituents(csv_text: str) -> list[dict[str, Any]]:
    """CSV rows → [{symbol, sector, industry}] in yfinance taxonomy.
    Symbols normalized for yfinance (BRK.B → BRK-B)."""
    out: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        symbol = (row.get("Symbol") or "").strip().upper().replace(".", "-")
        if not symbol:
            continue
        gics = (row.get("GICS Sector") or "").strip()
        out.append(
            {
                "symbol": symbol,
                "sector": GICS_TO_YF_SECTOR.get(gics),
                "industry": (row.get("GICS Sub-Industry") or "").strip() or None,
            }
        )
    return out


def fetch_sp500() -> list[dict[str, Any]]:
    """Current S&P 500 constituents, cached per trading day."""
    today = trading_day()
    if today in _sp500_cache:
        return _sp500_cache[today]
    response = httpx.get(CONSTITUENTS_CSV_URL, timeout=30, follow_redirects=True)
    response.raise_for_status()
    constituents = _parse_constituents(response.text)
    if len(constituents) < 400:  # sanity: a truncated/changed file, not the index
        raise ValueError(f"constituents CSV returned only {len(constituents)} rows")
    _sp500_cache.clear()
    _sp500_cache[today] = constituents
    return constituents


def fetch_universe(size: int | None) -> list[dict[str, Any]]:
    """Manual override list, or the S&P 500 (optionally trimmed to `size`)."""
    manual = [t.strip().upper() for t in settings.bull_screen_universe.split(",") if t.strip()]
    if manual:
        return [{"symbol": t, "sector": None, "industry": None} for t in manual]
    constituents = fetch_sp500()
    return constituents[:size] if size else constituents


def _records(df, tail: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ts, row in df.tail(tail).iterrows():
        out.append(
            {
                "date": ts.date().isoformat(),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
        )
    return out


def build_screen_facts(
    ticker: str, sector: str | None = None, industry: str | None = None
) -> dict[str, Any]:
    """The slice of the live facts bundle the strategies actually read.

    When the universe supplies sector/industry (S&P path) the fundamentals
    fetch is skipped entirely — earnings stay unknown (fail-open, see module
    docstring). Manual-list tickers fall back to the cached fundamentals tool
    for sector resolution and the earnings date.
    """
    df = get_price_history(ticker, PRICE_LOOKBACK_DAYS)
    days_until_earnings = None
    if sector is None:
        fundamentals = get_fundamentals(ticker)
        sector = fundamentals.get("sector")
        industry = fundamentals.get("industry")
        days_until_earnings = fundamentals.get("days_until_earnings")
    return {
        "ticker": ticker.upper(),
        "as_of": trading_day().isoformat(),
        "timeframe": "short",
        "prices": _records(df, PRICE_TAIL_BARS),
        "indicators": compute_indicators(df),
        "support_resistance": find_support_resistance(df),
        "fundamentals": {"days_until_earnings": days_until_earnings},
        "news": [],
        "supply_chain": {},
        "market_context": get_market_context(sector, industry),
    }


def _evaluate_one(entry: dict[str, Any]) -> dict[str, Any] | None:
    ticker = entry["symbol"]
    try:
        facts = build_screen_facts(ticker, entry.get("sector"), entry.get("industry"))
    except Exception as e:
        logger.warning("screen: skipping %s: %s", ticker, e)
        return None
    decisions = {name: fn(facts) for name, fn in REGISTRY.items()}
    active = decisions.get(settings.bull_active_strategy) or next(iter(decisions.values()))
    return {
        "ticker": ticker,
        "active": active,
        "others": {
            name: d.candidate_action for name, d in decisions.items() if d is not active
        },
        # Full decisions for non-active BUYs — the shadow-verdict feed (see
        # plan.md → Shadow verdict scoring). Kept whether or not active fired:
        # the overlap makes same-day strategy comparisons apples-to-apples.
        "shadow": {
            name: d
            for name, d in decisions.items()
            if d is not active and d.candidate_action == "BUY"
        },
    }


def rank_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure: split evaluated rows into ranked candidates vs collapsed holds,
    plus non-active-strategy BUYs as `shadow_candidates`."""
    candidates = []
    holds = []
    shadow_candidates = []
    for r in rows:
        for name, d in (r.get("shadow") or {}).items():
            shadow_candidates.append(
                {
                    "ticker": r["ticker"],
                    "strategy": name,
                    "base_confidence": d.base_confidence,
                    "reason": d.reason,
                    "entry": d.entry,
                    "stop": d.stop,
                    "target": d.target,
                    "reward_risk": d.reward_risk,
                    "filters": d.filters,
                    "setup": d.setup,
                }
            )
        d = r["active"]
        if d.candidate_action == "BUY":
            candidates.append(
                {
                    "ticker": r["ticker"],
                    "strategy": d.strategy,
                    "base_confidence": d.base_confidence,
                    "reason": d.reason,
                    "entry": d.entry,
                    "stop": d.stop,
                    "target": d.target,
                    "reward_risk": d.reward_risk,
                    "filters": d.filters,
                    "setup": d.setup,
                    "other_strategies": r["others"],
                }
            )
        else:
            holds.append({"ticker": r["ticker"], "reason": d.reason})
    candidates.sort(key=lambda c: (-(c["base_confidence"]), c["ticker"]))
    shadow_candidates.sort(key=lambda c: (-(c["base_confidence"]), c["ticker"], c["strategy"]))
    return {"candidates": candidates, "holds": holds, "shadow_candidates": shadow_candidates}


def run_screen(size: int | None = None, tickers: list[str] | None = None) -> dict[str, Any]:
    if tickers:
        universe = [{"symbol": t.upper(), "sector": None, "industry": None} for t in tickers]
    else:
        universe = fetch_universe(size if size is not None else settings.bull_screen_size or None)

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        rows = [r for r in pool.map(_evaluate_one, universe) if r is not None]

    ranked = rank_results(rows)
    return {
        "as_of": trading_day().isoformat(),
        "active_strategy": settings.bull_active_strategy,
        "universe_size": len(universe),
        "evaluated": len(rows),
        **ranked,
    }


def _cli() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--size", type=int, default=None, help="trim the S&P universe for a quick run"
    )
    parser.add_argument("--tickers", default=None, help="comma-separated manual universe")
    args = parser.parse_args()

    tickers = (
        [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None
    )
    report = run_screen(size=args.size, tickers=tickers)

    print(
        f"\nSCREEN {report['as_of']}   active: {report['active_strategy']}   "
        f"universe: {report['universe_size']} ({report['evaluated']} evaluated)"
    )
    if not report["candidates"]:
        print("\nNo setups today — the strategy is flat by design most days.")
    else:
        print(f"\n{len(report['candidates'])} candidate(s):")
        for c in report["candidates"]:
            print(
                f"  {c['ticker']:6s} conf={c['base_confidence']:>2d}  "
                f"entry={c['entry']:.2f} stop={c['stop']:.2f} target={c['target']:.2f} "
                f"rr={c['reward_risk']}  {c['reason']}"
            )
            print(f"         others: {c['other_strategies']}")
        print(
            "\nNext: POST /analyze {ticker, timeframe: 'short'} on the ones you "
            "like — that's the paid Opus veto/shade step."
        )
    if report["shadow_candidates"]:
        print(f"\n{len(report['shadow_candidates'])} shadow setup(s) from non-active strategies:")
        for c in report["shadow_candidates"]:
            print(f"  {c['ticker']:6s} {c['strategy']}  conf={c['base_confidence']:>2d}  {c['reason']}")
    failed = report["universe_size"] - report["evaluated"]
    if failed:
        print(f"\n({failed} ticker(s) skipped on data errors — see warnings above)")


if __name__ == "__main__":
    _cli()
