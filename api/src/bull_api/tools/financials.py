"""Multi-period financial series for the Financials charts. yfinance income
statement + balance sheet + cash flow (annual + quarterly), 24h TTL cache.
Free, no key required.

yfinance returns each statement as a DataFrame with metric rows and one column
per period (newest first), values in absolute USD. We walk the income statement
(Total Revenue gates a real period), then merge balance-sheet and cash-flow rows
for the same period column. Returned oldest→newest so the frontend renders
left-to-right.

Fields feed four TradingView-style panels:
  - Performance:        revenue, net_income (+ net margin derived on the client)
  - Revenue→profit:     cost_of_revenue, gross_profit, operating_expense,
                        operating_income, non_operating, tax, pretax_income
  - Debt & coverage:    total_debt, free_cash_flow, cash
  - Earnings:           eps (actual), report_date; estimate + surprise_pct are
                        enriched from Finnhub elsewhere (None without a key).
"""

import time
from typing import Any, TypedDict

import yfinance as yf


class FinancialPeriod(TypedDict):
    period: str  # "FY2026" (annual) or "Apr '26" (quarterly)
    report_date: str | None  # period-end date, YYYY-MM-DD
    revenue: float | None
    net_income: float | None
    ebitda: float | None
    # Revenue → profit conversion (income statement)
    cost_of_revenue: float | None
    gross_profit: float | None
    operating_expense: float | None
    operating_income: float | None
    non_operating: float | None
    tax: float | None
    pretax_income: float | None
    # Earnings
    eps: float | None
    estimate: float | None  # filled from Finnhub when available
    surprise_pct: float | None  # filled from Finnhub when available
    # Debt level & coverage (balance sheet + cash flow)
    total_debt: float | None
    free_cash_flow: float | None
    cash: float | None


class Financials(TypedDict):
    annual: list[FinancialPeriod]
    quarterly: list[FinancialPeriod]


_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, Financials]] = {}

_MAX_ANNUAL = 5
_MAX_QUARTERLY = 6


def _num(df: Any, row: str, col: Any) -> float | None:
    if df is None or getattr(df, "empty", True) or col is None or row not in df.index:
        return None
    try:
        v = float(df.loc[row, col])
    except (TypeError, ValueError, KeyError):
        return None
    return None if v != v else v  # NaN check


def _match_col(df: Any, target: Any) -> Any | None:
    """Find the column in `df` whose period-end date matches `target`'s date.

    yfinance usually labels the income statement, balance sheet and cash flow
    with identical period-end Timestamps, but quarter-end dates can drift by a
    day or two across statements — so match on the calendar date, tolerating a
    small gap, rather than requiring object identity.
    """
    if df is None or getattr(df, "empty", True):
        return None
    t = target.date() if hasattr(target, "date") else target
    best = None
    best_gap = 6  # days
    for col in df.columns:
        c = col.date() if hasattr(col, "date") else col
        try:
            gap = abs((c - t).days)
        except (TypeError, AttributeError):
            if c == t:
                return col
            continue
        if gap <= best_gap:
            best, best_gap = col, gap
    return best


def _first(df: Any, rows: tuple[str, ...], col: Any) -> float | None:
    """First non-None value across candidate row names for a period column."""
    for r in rows:
        v = _num(df, r, col)
        if v is not None:
            return v
    return None


def _series(
    income: Any,
    balance: Any,
    cash: Any,
    *,
    annual: bool,
    limit: int,
) -> list[FinancialPeriod]:
    if income is None or getattr(income, "empty", True):
        return []
    out: list[FinancialPeriod] = []
    # Income-statement columns are newest-first; walk oldest→newest, keep last `limit`.
    for col in reversed(list(income.columns)):
        revenue = _num(income, "Total Revenue", col)
        if revenue is None:
            continue  # yfinance pads the oldest column with NaNs — skip it
        bcol = _match_col(balance, col)
        ccol = _match_col(cash, col)
        out.append(
            {
                "period": _label(col, annual=annual),
                "report_date": _iso(col),
                "revenue": revenue,
                "net_income": _num(income, "Net Income", col),
                "ebitda": _num(income, "Normalized EBITDA", col)
                or _num(income, "EBITDA", col),
                "cost_of_revenue": _num(income, "Cost Of Revenue", col),
                "gross_profit": _num(income, "Gross Profit", col),
                "operating_expense": _num(income, "Operating Expense", col),
                "operating_income": _num(income, "Operating Income", col),
                "non_operating": _first(
                    income,
                    ("Other Income Expense", "Net Non Operating Interest Income Expense"),
                    col,
                ),
                "tax": _num(income, "Tax Provision", col),
                "pretax_income": _num(income, "Pretax Income", col),
                "eps": _num(income, "Diluted EPS", col) or _num(income, "Basic EPS", col),
                "estimate": None,
                "surprise_pct": None,
                "total_debt": _num(balance, "Total Debt", bcol),
                "free_cash_flow": _num(cash, "Free Cash Flow", ccol),
                "cash": _first(
                    balance,
                    (
                        "Cash And Cash Equivalents",
                        "Cash Cash Equivalents And Short Term Investments",
                    ),
                    bcol,
                ),
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


def _iso(col: Any) -> str | None:
    try:
        d = col.date() if hasattr(col, "date") else col
        return d.isoformat()
    except Exception:
        return None


def _safe(fn: Any) -> Any:
    """Fetch an optional yfinance statement; None on any failure so the income
    statement alone still produces a usable series (ETFs lack balance/cash)."""
    try:
        return fn()
    except Exception:
        return None


def get_financials(ticker: str) -> Financials:
    """Annual + quarterly financial series across the three statements, cached 24h."""
    key = ticker.upper()
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    tk = yf.Ticker(ticker)
    try:
        annual = _series(
            tk.income_stmt,
            _safe(lambda: tk.balance_sheet),
            _safe(lambda: tk.cashflow),
            annual=True,
            limit=_MAX_ANNUAL,
        )
        quarterly = _series(
            tk.quarterly_income_stmt,
            _safe(lambda: tk.quarterly_balance_sheet),
            _safe(lambda: tk.quarterly_cashflow),
            annual=False,
            limit=_MAX_QUARTERLY,
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
