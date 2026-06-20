"""Seasonality: cumulative year-to-date % return for the current year and the
two prior calendar years, overlaid on a common Jan→Dec axis (yfinance daily
closes, 24h TTL cache). Free, no key. Each year resets to 0% on Jan 1 so the
lines can be compared directly — descriptive statistics, not a forecast.
"""

import time
from datetime import UTC, datetime
from typing import TypedDict

import yfinance as yf

# All series are plotted against a single leap reference year so they overlay on
# one Jan→Dec x-axis (and Feb 29 survives). Frontend reads these as dates.
_REF_YEAR = 2000
_YEARS_BACK = 2  # current year + this many prior years


class SeasonalPoint(TypedDict):
    t: str  # "2000-MM-DD" reference-year date (shared Jan→Dec axis)
    v: float  # cumulative % from Jan 1 of that real year


class SeasonalYear(TypedDict):
    year: int  # real calendar year, e.g. 2026
    is_current: bool
    final_pct: float  # last point's cumulative % (for the legend)
    points: list[SeasonalPoint]


class Seasonals(TypedDict):
    years: list[SeasonalYear]  # ordered current-first


_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, Seasonals]] = {}
_MIN_POINTS = 20  # need ~a month of trading days for a usable current-year line


def get_seasonals(ticker: str) -> Seasonals:
    key = ticker.upper()
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    current_year = datetime.now(UTC).year
    start_year = current_year - _YEARS_BACK
    try:
        hist = yf.Ticker(ticker).history(
            start=f"{start_year}-01-01", interval="1d", auto_adjust=True
        )
        close = hist["Close"].dropna()
    except Exception as e:  # noqa: BLE001 — surface as a clean 404 upstream
        raise ValueError(f"No seasonal data available for {ticker!r}") from e

    if close.empty:
        raise ValueError(f"No seasonal data available for {ticker!r}")

    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)

    years: list[SeasonalYear] = []
    for y in range(current_year, start_year - 1, -1):
        s = close[close.index.year == y]
        if s.empty:
            continue
        base = float(s.iloc[0])
        if base <= 0:
            continue
        points: list[SeasonalPoint] = []
        for ts, px in s.items():
            # Map onto the reference year. Feb 29 only exists in leap years; the
            # reference year is a leap year so it always maps cleanly.
            points.append(
                {
                    "t": f"{_REF_YEAR:04d}-{ts.month:02d}-{ts.day:02d}",
                    "v": round((float(px) / base - 1.0) * 100, 2),
                }
            )
        years.append(
            {
                "year": int(y),
                "is_current": y == current_year,
                "final_pct": points[-1]["v"],
                "points": points,
            }
        )

    if not years or sum(len(yr["points"]) for yr in years) < _MIN_POINTS:
        raise ValueError(f"Not enough history for seasonals on {ticker!r}")

    result: Seasonals = {"years": years}
    _cache[key] = (now, result)
    return result


if __name__ == "__main__":
    import sys

    print(get_seasonals(sys.argv[1] if len(sys.argv) > 1 else "NVDA"))
