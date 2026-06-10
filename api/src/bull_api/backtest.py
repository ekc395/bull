"""Strategy tournament backtester — the finalization tool for short mode.

Replays every registered strategy (`bull_api.strategy.REGISTRY`) over daily
yfinance history and simulates the full trade lifecycle the live system
executes (bracket stop/target + time stop). No LLM anywhere in this module —
that's the point: deterministic rules have no training-data contamination, so
unlike the verdict pipeline they CAN be backtested honestly. The LLM
veto/shade overlay is forward-tested only (see scoring.py / plan.md).

Point-in-time discipline:
  - `build_facts_asof` slices each series up to day t and reuses the SAME
    functions as the live bundle (`compute_indicators`,
    `find_support_resistance`) over the same trailing window — no
    reimplemented math.
  - A signal computed on the close of day t fills at the OPEN of day t+1.
  - Exits on daily OHLC, conservatively: a bar that touches both stop and
    target counts as a stop; gaps through a level fill at the open.
  - If the next open already gaps through the stop or target, the entry is
    skipped (the bracket would fill instantly for ~0 edge).

Fidelity bounds (accepted, see plan.md): daily resolution, no slippage model,
yfinance earnings dates are sparse for older history (the earnings filter
fails open, same as live), and a hand-picked watchlist of today's names is
mildly survivorship-biased — fine for RANKING strategies on a shared universe,
not for absolute-return claims.

Run: cd api && python -m bull_api.backtest --start 2022-01-01
"""

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

import pandas as pd
import yfinance as yf

from .strategy import REGISTRY
from .strategy.base import StrategyDecision
from .tools.indicators import compute_indicators
from .tools.market_context import _resolve_sector_etf, _vix_state
from .tools.support_resistance import find_support_resistance

logger = logging.getLogger(__name__)

# Mirror the live short-mode bundle: ~400 calendar days fetched ≈ this many
# trading bars for indicators/S&R; 60 stored price bars (agent._PRICE_TAIL_BARS).
LOOKBACK_BARS = 270
PRICE_TAIL_BARS = 60
WARMUP_CALENDAR_DAYS = 650  # fetched before --start so day 1 has a full window

# Used when settings (and the BULL_WATCHLIST env) are unavailable; kept in sync
# with config.Settings.bull_watchlist.
DEFAULT_TICKERS = "AAPL,MSFT,NVDA,AMZN,META,JPM,UNH,XOM"


# --- point-in-time facts -------------------------------------------------------


def _records(window: pd.DataFrame, tail: int) -> list[dict[str, Any]]:
    """OHLCV rows → the same record shape agent._prices_to_records produces."""
    out: list[dict[str, Any]] = []
    for ts, row in window.tail(tail).iterrows():
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


def build_facts_asof(
    ticker: str,
    df: pd.DataFrame,
    i: int,
    *,
    spy_above_sma_50: bool | None,
    sector_etf: str | None,
    sector_above_sma_50: bool | None,
    vix_level: float | None,
    days_until_earnings: int | None,
) -> dict[str, Any]:
    """Facts bundle as the live agent would have seen it at the close of bar i.

    Indicators and S/R are computed over the trailing LOOKBACK_BARS window
    ending at bar i — the live contract (full fetch frame, not the stored
    60-bar tail). Strictly no data past bar i.
    """
    window = df.iloc[max(0, i - LOOKBACK_BARS + 1) : i + 1]
    return {
        "ticker": ticker.upper(),
        "as_of": df.index[i].date().isoformat(),
        "timeframe": "short",
        "prices": _records(window, PRICE_TAIL_BARS),
        "indicators": compute_indicators(window),
        "support_resistance": find_support_resistance(window),
        "fundamentals": {"days_until_earnings": days_until_earnings},
        "news": [],
        "supply_chain": {},
        "market_context": {
            "spy": {"above_sma_50": spy_above_sma_50},
            "sector_etf": sector_etf,
            "sector": {"above_sma_50": sector_above_sma_50} if sector_etf else None,
            "vix_level": vix_level,
            "vix_state": _vix_state(vix_level),
        },
    }


# --- simulation core (pure; unit-tested without network) -------------------------


@dataclass(frozen=True)
class Trade:
    ticker: str
    strategy: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    exit_reason: str  # stop | target | time_stop | end_of_data
    return_pct: float
    hold_bars: int
    confidence: int

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SimResult:
    trades: list[Trade]
    days_evaluated: int
    signals: int


def simulate(
    df: pd.DataFrame,
    decide: Callable[[int], StrategyDecision | None],
    *,
    ticker: str = "?",
    strategy: str = "?",
    start_idx: int = 0,
) -> SimResult:
    """Walk bars [start_idx, end), one open position at a time.

    `decide(i)` is called only while flat and only with information through
    bar i's close (the caller guarantees that via build_facts_asof); a BUY
    fills at the open of bar i+1.
    """
    o = df["Open"].to_numpy(dtype=float)
    h = df["High"].to_numpy(dtype=float)
    lo = df["Low"].to_numpy(dtype=float)
    c = df["Close"].to_numpy(dtype=float)
    n = len(df)

    trades: list[Trade] = []
    days_evaluated = 0
    signals = 0
    pos: dict[str, Any] | None = None

    def close_out(i: int, price: float, reason: str) -> None:
        nonlocal pos
        assert pos is not None
        trades.append(
            Trade(
                ticker=ticker,
                strategy=strategy,
                entry_date=df.index[pos["entry_idx"]].date().isoformat(),
                entry_price=round(pos["entry_price"], 4),
                exit_date=df.index[i].date().isoformat(),
                exit_price=round(price, 4),
                exit_reason=reason,
                return_pct=round((price / pos["entry_price"] - 1.0) * 100.0, 4),
                hold_bars=i - pos["entry_idx"],
                confidence=pos["confidence"],
            )
        )
        pos = None

    for i in range(start_idx, n):
        if pos is not None:
            past_entry_bar = i > pos["entry_idx"]
            if past_entry_bar and o[i] <= pos["stop"]:
                close_out(i, o[i], "stop")  # gapped through the stop
            elif past_entry_bar and o[i] >= pos["target"]:
                close_out(i, o[i], "target")  # gapped through the target
            elif lo[i] <= pos["stop"]:
                close_out(i, pos["stop"], "stop")  # stop-first on ambiguous bars
            elif h[i] >= pos["target"]:
                close_out(i, pos["target"], "target")
            elif i - pos["entry_idx"] >= pos["max_hold"]:
                close_out(i, c[i], "time_stop")

        if pos is None and i < n - 1:
            days_evaluated += 1
            d = decide(i)
            if (
                d is not None
                and d.candidate_action == "BUY"
                and d.stop is not None
                and d.target is not None
            ):
                signals += 1
                entry = o[i + 1]
                if entry <= d.stop or entry >= d.target:
                    continue  # overnight gap through a bracket leg — no edge left
                pos = {
                    "entry_idx": i + 1,
                    "entry_price": entry,
                    "stop": d.stop,
                    "target": d.target,
                    "max_hold": d.max_hold_trading_days,
                    "confidence": d.base_confidence,
                }

    if pos is not None and pos["entry_idx"] <= n - 1:
        close_out(n - 1, c[n - 1], "end_of_data")

    return SimResult(trades=trades, days_evaluated=days_evaluated, signals=signals)


# --- aggregation -----------------------------------------------------------------


def _max_drawdown_pct(returns_pct: list[float]) -> float | None:
    """Max drawdown of an equity curve that compounds the trades in order."""
    if not returns_pct:
        return None
    equity = peak = 1.0
    worst = 0.0
    for r in returns_pct:
        equity *= 1.0 + r / 100.0
        peak = max(peak, equity)
        worst = min(worst, (equity - peak) / peak)
    return round(worst * 100.0, 2)


def strategy_summary(results: dict[str, SimResult]) -> dict[str, Any]:
    """Aggregate one strategy's per-ticker SimResults into the report row."""
    trades = sorted(
        (t for r in results.values() for t in r.trades), key=lambda t: t.exit_date
    )
    days = sum(r.days_evaluated for r in results.values())
    signals = sum(r.signals for r in results.values())
    rets = [t.return_pct for t in trades]
    wins = [r for r in rets if r > 0]
    compounded = 1.0
    for r in rets:
        compounded *= 1.0 + r / 100.0
    exits: dict[str, int] = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
    return {
        "trades": len(trades),
        "days_evaluated": days,
        "fire_rate_pct": round(100.0 * signals / days, 2) if days else None,
        "win_rate": round(len(wins) / len(rets), 4) if rets else None,
        "avg_return_pct": round(sum(rets) / len(rets), 3) if rets else None,
        "median_return_pct": round(sorted(rets)[len(rets) // 2], 3) if rets else None,
        "total_return_pct": round((compounded - 1.0) * 100.0, 2) if rets else None,
        "max_drawdown_pct": _max_drawdown_pct(rets),
        "avg_hold_bars": round(sum(t.hold_bars for t in trades) / len(trades), 1)
        if trades
        else None,
        "exit_reasons": exits,
        "per_ticker": {
            tick: {
                "trades": len(r.trades),
                "avg_return_pct": round(
                    sum(t.return_pct for t in r.trades) / len(r.trades), 3
                )
                if r.trades
                else None,
            }
            for tick, r in sorted(results.items())
        },
        "trade_log": [t.to_json() for t in trades],
    }


# --- data assembly (network) --------------------------------------------------------


def _fetch_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    df = yf.Ticker(symbol).history(
        start=(start - timedelta(days=WARMUP_CALENDAR_DAYS)).isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
    )
    if df is None or df.empty:
        raise ValueError(f"no price data for {symbol!r}")
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.tz_localize(None)
    return df


def _above_sma_50_by_day(close: pd.Series, on: pd.DatetimeIndex) -> pd.Series:
    sma = close.rolling(50).mean()
    above = (close > sma).astype(object)
    above[sma.isna()] = None
    return above.reindex(on, method="ffill")


def _earnings_dates(ticker: str) -> list[date]:
    try:
        ed = yf.Ticker(ticker).get_earnings_dates(limit=60)
    except Exception:
        return []
    if ed is None or ed.empty:
        return []
    return sorted({ts.date() for ts in ed.index})


def _days_until_earnings(t: date, dates: list[date]) -> int | None:
    """Signed calendar days to the nearest relevant print, live convention:
    positive = upcoming, small negative = just reported, None = unknown."""
    recent = max((d for d in dates if d < t), default=None)
    if recent is not None and (t - recent).days <= 7:
        return -(t - recent).days
    upcoming = min((d for d in dates if d >= t), default=None)
    if upcoming is not None:
        return (upcoming - t).days
    return None


def run_backtest(
    tickers: list[str],
    start: date,
    end: date,
    strategies: dict[str, Callable[[dict[str, Any]], StrategyDecision]] | None = None,
) -> dict[str, Any]:
    strategies = strategies or dict(REGISTRY)

    spy = _fetch_history("SPY", start, end)
    try:
        vix_close = _fetch_history("^VIX", start, end)["Close"]
    except ValueError:
        vix_close = pd.Series(dtype=float)

    per_strategy: dict[str, dict[str, SimResult]] = {name: {} for name in strategies}
    skipped: list[str] = []

    for ticker in tickers:
        try:
            df = _fetch_history(ticker, start, end)
        except Exception as e:
            logger.warning("skipping %s: %s", ticker, e)
            skipped.append(ticker)
            continue

        # Sector ETF via the live mapping; .info is best-effort (None → the
        # sector filter fails closed, same as a live fetch failure would).
        try:
            info = yf.Ticker(ticker).info or {}
        except Exception:
            info = {}
        sector_etf = _resolve_sector_etf(info.get("sector"), info.get("industry"))
        sector_above = pd.Series(index=df.index, dtype=object)
        if sector_etf:
            try:
                etf_close = _fetch_history(sector_etf, start, end)["Close"]
                sector_above = _above_sma_50_by_day(etf_close, df.index)
            except Exception:
                sector_etf = None

        spy_above = _above_sma_50_by_day(spy["Close"], df.index)
        vix_by_day = vix_close.reindex(df.index, method="ffill")
        earnings = _earnings_dates(ticker)

        start_idx = int((df.index.date < start).sum())
        facts_cache: dict[int, dict[str, Any]] = {}

        def facts_for(i: int) -> dict[str, Any]:
            if i not in facts_cache:
                vix = vix_by_day.iloc[i] if len(vix_by_day) else None
                facts_cache[i] = build_facts_asof(
                    ticker,
                    df,
                    i,
                    spy_above_sma_50=None
                    if pd.isna(spy_above.iloc[i])
                    else bool(spy_above.iloc[i]),
                    sector_etf=sector_etf,
                    sector_above_sma_50=None
                    if (not sector_etf or pd.isna(sector_above.iloc[i]))
                    else bool(sector_above.iloc[i]),
                    vix_level=None if vix is None or pd.isna(vix) else round(float(vix), 2),
                    days_until_earnings=_days_until_earnings(
                        df.index[i].date(), earnings
                    ),
                )
            return facts_cache[i]

        for name, evaluate in strategies.items():
            per_strategy[name][ticker] = simulate(
                df,
                lambda i, _eval=evaluate: _eval(facts_for(i)),
                ticker=ticker,
                strategy=name,
                start_idx=start_idx,
            )
        facts_cache.clear()

    spy_in_range = spy[spy.index.date >= start]["Close"]
    spy_return = (
        round((float(spy_in_range.iloc[-1]) / float(spy_in_range.iloc[0]) - 1.0) * 100.0, 2)
        if len(spy_in_range) >= 2
        else None
    )

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "tickers": [t for t in tickers if t not in skipped],
        "skipped": skipped,
        "universe_note": (
            "hand-picked current names: mildly survivorship-biased — "
            "use for ranking strategies, not absolute-return claims"
        ),
        "strategies": {name: strategy_summary(res) for name, res in per_strategy.items()},
        "benchmark": {"spy_buy_hold_return_pct": spy_return},
    }


# --- CLI ----------------------------------------------------------------------------


def _fmt(v: Any, suffix: str = "") -> str:
    return "—" if v is None else f"{v}{suffix}"


def _print_report(report: dict[str, Any], verbose: bool) -> None:
    print(
        f"\nBACKTEST {report['start']} → {report['end']}   "
        f"tickers: {','.join(report['tickers'])}"
    )
    if report["skipped"]:
        print(f"skipped (no data): {','.join(report['skipped'])}")
    print(f"note: {report['universe_note']}\n")
    print(
        f"{'strategy':14s} {'trades':>6s} {'fire%':>6s} {'win%':>6s} {'avg%':>7s} "
        f"{'med%':>7s} {'total%':>8s} {'maxDD%':>7s} {'hold':>5s}  exits (stop/target/time/eod)"
    )
    for name, s in report["strategies"].items():
        ex = s["exit_reasons"]
        exits = "/".join(
            str(ex.get(k, 0)) for k in ("stop", "target", "time_stop", "end_of_data")
        )
        win = None if s["win_rate"] is None else round(s["win_rate"] * 100, 1)
        print(
            f"{name:14s} {s['trades']:>6d} {_fmt(s['fire_rate_pct']):>6s} {_fmt(win):>6s} "
            f"{_fmt(s['avg_return_pct']):>7s} {_fmt(s['median_return_pct']):>7s} "
            f"{_fmt(s['total_return_pct']):>8s} {_fmt(s['max_drawdown_pct']):>7s} "
            f"{_fmt(s['avg_hold_bars']):>5s}  {exits}"
        )
    print(
        f"\nSPY buy-and-hold over the same window: "
        f"{_fmt(report['benchmark']['spy_buy_hold_return_pct'], '%')}"
    )
    if verbose:
        for name, s in report["strategies"].items():
            print(f"\n{name} per ticker:")
            for tick, row in s["per_ticker"].items():
                print(
                    f"  {tick:6s} trades={row['trades']:>3d} "
                    f"avg={_fmt(row['avg_return_pct'], '%')}"
                )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument(
        "--tickers", default=None, help="comma-separated; default: BULL_WATCHLIST"
    )
    parser.add_argument(
        "--strategies", default=None, help=f"comma-separated subset of {list(REGISTRY)}"
    )
    parser.add_argument("--json", default=None, help="also write the full report here")
    parser.add_argument("--verbose", action="store_true", help="per-ticker breakdown")
    args = parser.parse_args()

    if args.tickers:
        raw = args.tickers
    else:
        try:  # settings needs a populated .env; the CLI shouldn't require one
            from .config import settings

            raw = getattr(settings, "bull_watchlist", DEFAULT_TICKERS)
        except Exception:
            raw = DEFAULT_TICKERS
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]

    strategies = dict(REGISTRY)
    if args.strategies:
        wanted = {s.strip() for s in args.strategies.split(",") if s.strip()}
        unknown = wanted - strategies.keys()
        if unknown:
            parser.error(f"unknown strategies {sorted(unknown)}; have {list(REGISTRY)}")
        strategies = {k: v for k, v in strategies.items() if k in wanted}

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    report = run_backtest(tickers, start, end, strategies)
    _print_report(report, args.verbose)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nfull report (incl. trade logs) → {args.json}")


if __name__ == "__main__":
    main()
