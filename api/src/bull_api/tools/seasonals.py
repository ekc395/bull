"""Seasonality: average return per calendar month over ~10 years of monthly
closes (yfinance), 24h TTL cache. Free, no key. Surfaces recurring monthly
tendencies — descriptive statistics, not a forecast.
"""

import calendar
import time
from typing import TypedDict

import yfinance as yf


class SeasonalMonth(TypedDict):
    month: int  # 1-12
    label: str  # "Jan"
    avg_return_pct: float  # mean monthly return, in percent
    positive_rate: float  # fraction of sampled years that were positive (0..1)
    sample: int  # number of years contributing


class Seasonals(TypedDict):
    years: int  # distinct calendar years sampled
    months: list[SeasonalMonth]


_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, Seasonals]] = {}
_MIN_MONTHS = 24  # need ~2y of monthly returns for a meaningful average


def get_seasonals(ticker: str) -> Seasonals:
    key = ticker.upper()
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    try:
        hist = yf.Ticker(ticker).history(
            period="10y", interval="1mo", auto_adjust=True
        )
        close = hist["Close"].dropna()
    except Exception as e:  # noqa: BLE001 — surface as a clean 404 upstream
        raise ValueError(f"No seasonal data available for {ticker!r}") from e

    returns = close.pct_change().dropna()
    if len(returns) < _MIN_MONTHS:
        raise ValueError(f"Not enough history for seasonals on {ticker!r}")

    returns.index = returns.index.tz_localize(None)
    by_month = returns.groupby(returns.index.month)

    months: list[SeasonalMonth] = []
    for m in range(1, 13):
        if m not in by_month.groups:
            continue
        s = by_month.get_group(m)
        months.append(
            {
                "month": m,
                "label": calendar.month_abbr[m],
                "avg_return_pct": round(float(s.mean()) * 100, 2),
                "positive_rate": round(float((s > 0).sum()) / len(s), 3),
                "sample": int(len(s)),
            }
        )

    result: Seasonals = {"years": int(returns.index.year.nunique()), "months": months}
    _cache[key] = (now, result)
    return result


if __name__ == "__main__":
    import sys

    print(get_seasonals(sys.argv[1] if len(sys.argv) > 1 else "NVDA"))
