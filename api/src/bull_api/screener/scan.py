"""Free pre-filter pass over the S&P 500 universe.

No LLM calls — just bulk yfinance pull -> compute indicators -> apply strict
screen. The output drives the user's confirmation prompt; only the survivors
get analyzed by Claude (in routers/screener.py).
"""

import asyncio
import logging
from dataclasses import dataclass

import pandas as pd
import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..tools.indicators import compute_indicators
from .constituents import Constituent, get_constituents
from .costs import estimate_scan_cost_usd
from .filter import passes_strict_filter

logger = logging.getLogger(__name__)

# Tuned by hand: 50 at a time keeps the Yahoo response under the 1MB-ish payload
# limit we've seen and parallelizes nicely. Below 25 the request-per-second rate
# bites; above 100 we get back DataFrames with mostly NaN.
CHUNK_SIZE = 50

# Hard ceiling on candidates surfaced to the user. Strict filter usually returns
# 10-25 in normal markets; if it returns more we trim before estimating cost so
# the confirmation prompt can't blow past the user's expected spend.
MAX_CANDIDATES = 30


@dataclass(frozen=True)
class Candidate:
    symbol: str
    company_name: str
    sector: str
    close: float
    rsi_14: float
    macd_hist: float
    sma_50: float
    sma_200: float
    volume_current: float
    volume_20d_avg: float


@dataclass(frozen=True)
class ScanResult:
    candidates: list[Candidate]
    universe_size: int
    filtered_out: int
    overflowed: bool  # strict filter returned > MAX_CANDIDATES and we trimmed
    errors: list[str]
    estimated_cost_usd: float
    model: str


def _download_chunk(symbols: list[str]) -> pd.DataFrame | None:
    df = yf.download(
        tickers=symbols,
        period="2y",
        interval="1d",
        group_by="ticker",
        threads=True,
        auto_adjust=True,
        progress=False,
        timeout=20,
    )
    if df is None or df.empty:
        return None
    return df


def _frame_for_symbol(bulk: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
    """Extract a single ticker's OHLCV frame from yfinance's multi-level result."""
    try:
        sub = bulk[symbol] if symbol in bulk.columns.get_level_values(0) else bulk
    except (KeyError, AttributeError):
        return None
    if sub is None or sub.empty:
        return None
    cols = {"Open", "High", "Low", "Close", "Volume"}
    if not cols.issubset(sub.columns):
        return None
    sub = sub[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if len(sub) < 200:
        return None
    return sub


def _evaluate(constituent: Constituent, frame: pd.DataFrame) -> Candidate | None:
    snap = compute_indicators(frame)
    close = float(frame["Close"].iloc[-1])
    if not passes_strict_filter(snap, close):
        return None
    return Candidate(
        symbol=constituent.symbol,
        company_name=constituent.company_name,
        sector=constituent.sector,
        close=round(close, 2),
        rsi_14=round(snap["rsi_14"], 2),  # type: ignore[arg-type]
        macd_hist=round(snap["macd_hist"], 4),  # type: ignore[arg-type]
        sma_50=round(snap["sma_50"], 2),  # type: ignore[arg-type]
        sma_200=round(snap["sma_200"], 2),  # type: ignore[arg-type]
        volume_current=float(snap["volume_current"] or 0.0),
        volume_20d_avg=float(snap["volume_20d_avg"] or 0.0),
    )


def _run_sync(constituents: list[Constituent]) -> tuple[list[Candidate], list[str]]:
    candidates: list[Candidate] = []
    errors: list[str] = []

    by_symbol = {c.symbol: c for c in constituents}
    symbols = list(by_symbol.keys())

    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i : i + CHUNK_SIZE]
        try:
            bulk = _download_chunk(chunk)
        except Exception as e:
            logger.warning("screener chunk %d-%d download failed: %s", i, i + len(chunk), e)
            errors.append(f"chunk {i}-{i + len(chunk)}: {e}")
            continue
        if bulk is None:
            errors.append(f"chunk {i}-{i + len(chunk)}: no data")
            continue
        for sym in chunk:
            frame = _frame_for_symbol(bulk, sym)
            if frame is None:
                continue
            try:
                cand = _evaluate(by_symbol[sym], frame)
            except Exception as e:
                logger.warning("screener evaluation failed for %s: %s", sym, e)
                errors.append(f"{sym}: {e}")
                continue
            if cand is not None:
                candidates.append(cand)

    candidates.sort(key=lambda c: c.rsi_14)
    return candidates, errors


async def run_preview(session: AsyncSession) -> ScanResult:
    """Free pre-filter pass. No LLM calls.

    Refreshes the constituent universe if stale (>7 days), then bulk-downloads
    2y of OHLCV in chunks and evaluates the strict screen on each ticker.
    """
    constituents = await get_constituents(session)
    universe_size = len(constituents)

    candidates, errors = await asyncio.to_thread(_run_sync, constituents)
    pre_trim = len(candidates)
    overflowed = pre_trim > MAX_CANDIDATES
    if overflowed:
        candidates = candidates[:MAX_CANDIDATES]

    return ScanResult(
        candidates=candidates,
        universe_size=universe_size,
        filtered_out=universe_size - pre_trim,
        overflowed=overflowed,
        errors=errors,
        estimated_cost_usd=estimate_scan_cost_usd(len(candidates), settings.bull_model),
        model=settings.bull_model,
    )
