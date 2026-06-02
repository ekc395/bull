"""Multi-year financial series for the Financials charts. yfinance income
statement (annual + quarterly), 24h TTL cache. Free, no key required.

yfinance returns each statement as a DataFrame with metric rows and one column
per period (newest first), values in absolute USD. We pull Total Revenue, Net
Income and EBITDA, drop padding/NaN columns, and return oldest→newest so the
frontend can render left-to-right bars.
"""

import time
from typing import Any, TypedDict

import yfinance as yf


class FinancialPeriod(TypedDict):
    period: str  # "FY2026" (annual) or "Apr '26" (quarterly)
    revenue: float | None
    net_income: float | None
    ebitda: float | None


class Financials(TypedDict):
    annual: list[FinancialPeriod]
    quarterly: list[FinancialPeriod]


_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, Financials]] = {}

_MAX_ANNUAL = 5
_MAX_QUARTERLY = 6


def _num(df: Any, row: str, col: Any) -> float | None:
    if row not in df.index:
        return None
    try:
        v = float(df.loc[row, col])
    except (TypeError, ValueError):
        return None
    return None if v != v else v  # NaN check


def _series(df: Any, *, annual: bool, limit: int) -> list[FinancialPeriod]:
    if df is None or getattr(df, "empty", True):
        return []
    out: list[FinancialPeriod] = []
    # Columns are newest-first; walk oldest→newest and keep the last `limit`.
    for col in reversed(list(df.columns)):
        revenue = _num(df, "Total Revenue", col)
        if revenue is None:
            continue  # yfinance pads the oldest column with NaNs — skip it
        out.append(
            {
                "period": _label(col, annual=annual),
                "revenue": revenue,
                "net_income": _num(df, "Net Income", col),
                "ebitda": _num(df, "Normalized EBITDA", col) or _num(df, "EBITDA", col),
            }
        )
    return out[-limit:]


def _label(col: Any, *, annual: bool) -> str:
    try:
        d = col.date() if hasattr(col, "date") else col
        if annual:
            return f"FY{d.year}"
        return d.strftime("%b '%y")
    except Exception:
        return str(col)


def get_financials(ticker: str) -> Financials:
    """Annual + quarterly revenue/net-income/EBITDA series, cached 24h."""
    key = ticker.upper()
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    tk = yf.Ticker(ticker)
    try:
        annual = _series(tk.income_stmt, annual=True, limit=_MAX_ANNUAL)
        quarterly = _series(
            tk.quarterly_income_stmt, annual=False, limit=_MAX_QUARTERLY
        )
    except Exception as e:  # noqa: BLE001 — surface as a clean 404 upstream
        raise ValueError(f"No financials available for {ticker!r}") from e

    if not annual and not quarterly:
        raise ValueError(f"No financials available for {ticker!r}")

    result: Financials = {"annual": annual, "quarterly": quarterly}
    _cache[key] = (now, result)
    return result


if __name__ == "__main__":
    import sys

    print(get_financials(sys.argv[1] if len(sys.argv) > 1 else "NVDA"))
