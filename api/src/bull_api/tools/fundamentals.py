"""Fundamentals: Finnhub primary → yfinance → Alpha Vantage. 24h TTL cache.

Finnhub gives the cleanest data (Refinitiv-backed) on a generous free tier
(60 req/min). yfinance is the no-key fallback. Alpha Vantage is last resort
because its 25 calls/day quota is tight.
"""

import time
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypedDict

import httpx
import yfinance as yf

from ..config import settings
from ..time import trading_day


class Fundamentals(TypedDict, total=False):
    name: str  # Full company name, e.g. "NVIDIA Corporation".
    sector: str
    industry: str
    market_cap: float
    trailing_pe: float | None
    forward_pe: float | None
    profit_margins: float | None
    revenue_growth: float | None
    earnings_date: str | None
    # Signed days from today to next earnings. Negative = recently reported.
    # None if the source didn't return a date or the date is implausibly stale.
    days_until_earnings: int | None
    # Analyst consensus (best-effort, yfinance / Refinitiv panel).
    analyst_target_mean: float | None
    analyst_target_high: float | None
    analyst_target_low: float | None
    analyst_count: int | None
    # 1.0 = strong buy, 3.0 = hold, 5.0 = strong sell.
    recommendation_mean: float | None
    recommendation_key: str | None
    # Extra key stats lifted from yfinance info (TradingView "Key stats" parity).
    beta: float | None
    eps_ttm: float | None
    dividend_yield: float | None  # in percent units (0.47 → 0.47%), per yfinance
    shares_float: float | None
    shares_outstanding: float | None
    net_income: float | None
    total_revenue: float | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    # Company profile for the "About" card (yfinance info; ipo from Finnhub).
    description: str | None
    website: str | None
    ceo: str | None
    headquarters: str | None  # "City, ST" (US) or "City, Country"
    employees: int | None
    ipo_date: str | None  # YYYY-MM-DD
    source: str  # "finnhub" | "yfinance" | "alphavantage"


_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, Fundamentals]] = {}


def _to_float(x: Any) -> float | None:
    if x is None or x == "None" or x == "":
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN check


def _from_finnhub(ticker: str) -> Fundamentals | None:
    """Finnhub: cleanest free fundamentals source. Needs FINNHUB_API_KEY."""
    if not settings.finnhub_api_key:
        return None
    base = "https://finnhub.io/api/v1"
    token = settings.finnhub_api_key
    today = trading_day()
    horizon = today + timedelta(days=120)

    try:
        with httpx.Client(timeout=10.0) as client:
            profile = client.get(
                f"{base}/stock/profile2",
                params={"symbol": ticker, "token": token},
            ).json()
            metric = client.get(
                f"{base}/stock/metric",
                params={"symbol": ticker, "metric": "all", "token": token},
            ).json()
            cal = client.get(
                f"{base}/calendar/earnings",
                params={
                    "symbol": ticker,
                    "from": today.isoformat(),
                    "to": horizon.isoformat(),
                    "token": token,
                },
            ).json()
    except Exception:
        return None

    if not profile or not profile.get("marketCapitalization"):
        return None

    m = (metric or {}).get("metric", {}) or {}
    earnings_list = (cal or {}).get("earningsCalendar") or []
    earnings_date = earnings_list[0].get("date") if earnings_list else None

    # Finnhub's marketCapitalization is in **millions** of USD.
    mcap_m = _to_float(profile.get("marketCapitalization"))
    market_cap = (mcap_m or 0.0) * 1_000_000

    # Finnhub returns margins/growth as percents (55.6); yfinance/AV use fractions (0.556).
    # Normalize to fractions so downstream consumers don't have to know the source.
    margin_pct = _to_float(m.get("netProfitMarginTTM"))
    growth_pct = _to_float(m.get("revenueGrowthQuarterlyYoy")) or _to_float(
        m.get("revenueGrowthTTMYoy")
    )

    return {
        "name": profile.get("name") or "",
        "sector": "",  # Finnhub doesn't return a separate sector; only finnhubIndustry.
        "industry": profile.get("finnhubIndustry") or "",
        "market_cap": market_cap,
        "trailing_pe": _to_float(m.get("peTTM")) or _to_float(m.get("peBasicExclExtraTTM")),
        # Finnhub's free tier exposes peNormalizedAnnual but not analyst-estimate-based
        # forward P/E — using it would equal trailing and mislead the agent. Leave None.
        "forward_pe": None,
        "profit_margins": margin_pct / 100 if margin_pct is not None else None,
        "revenue_growth": growth_pct / 100 if growth_pct is not None else None,
        "earnings_date": earnings_date,
        "website": profile.get("weburl") or None,
        "ipo_date": profile.get("ipo") or None,
        "source": "finnhub",
    }


def _from_yfinance(ticker: str) -> Fundamentals | None:
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return None
    if not info or not info.get("marketCap"):
        return None

    earnings_ts = info.get("earningsTimestamp")
    earnings_date: str | None = None
    if earnings_ts:
        try:
            earnings_date = datetime.fromtimestamp(int(earnings_ts), tz=UTC).date().isoformat()
        except (TypeError, ValueError, OSError):
            pass

    return {
        "name": info.get("longName") or info.get("shortName") or "",
        "sector": info.get("sector") or "",
        "industry": info.get("industry") or "",
        "market_cap": _to_float(info.get("marketCap")) or 0.0,
        "trailing_pe": _to_float(info.get("trailingPE")),
        "forward_pe": _to_float(info.get("forwardPE")),
        "profit_margins": _to_float(info.get("profitMargins")),
        "revenue_growth": _to_float(info.get("revenueGrowth")),
        "earnings_date": earnings_date,
        "source": "yfinance",
    }


def _from_alphavantage(ticker: str) -> Fundamentals | None:
    if not settings.alphavantage_api_key:
        return None
    url = "https://www.alphavantage.co/query"
    params = {"function": "OVERVIEW", "symbol": ticker, "apikey": settings.alphavantage_api_key}
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    if not data or not data.get("MarketCapitalization"):
        return None

    return {
        "name": data.get("Name") or "",
        "sector": data.get("Sector") or "",
        "industry": data.get("Industry") or "",
        "market_cap": _to_float(data.get("MarketCapitalization")) or 0.0,
        "trailing_pe": _to_float(data.get("TrailingPE")) or _to_float(data.get("PERatio")),
        "forward_pe": _to_float(data.get("ForwardPE")),
        "profit_margins": _to_float(data.get("ProfitMargin")),
        "revenue_growth": _to_float(data.get("QuarterlyRevenueGrowthYOY")),
        "earnings_date": None,
        "source": "alphavantage",
    }


def _backfill_forward_pe(result: Fundamentals, ticker: str) -> Fundamentals:
    """Best-effort forward P/E from yfinance's Refinitiv-licensed feed.

    Finnhub's free tier doesn't expose analyst-estimate-based forward P/E
    (it's gated behind their paid plan). yfinance scrapes Yahoo Finance,
    which licenses the same Refinitiv consensus panel, so its `forwardPE`
    field is the best free approximation. Called only when the primary
    source didn't already provide one.
    """
    if result.get("forward_pe") is not None:
        return result
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return result
    fp = _to_float(info.get("forwardPE"))
    if fp is not None:
        result["forward_pe"] = fp
    return result


def _compute_days_until_earnings(earnings_date: str | None) -> int | None:
    """Signed day delta from today (ET) to earnings_date. Clamped to ±90 days
    so implausibly stale yfinance entries don't pollute the bundle."""
    if not earnings_date:
        return None
    try:
        ed = date.fromisoformat(earnings_date)
    except ValueError:
        return None
    delta = (ed - trading_day()).days
    if delta < -30 or delta > 180:
        return None
    return delta


def _backfill_analyst_targets(result: Fundamentals, ticker: str) -> Fundamentals:
    """Pull analyst price targets + recommendation grade from yfinance, and
    backfill `sector` when Finnhub left it empty.

    Finnhub doesn't return a separate sector field (only `finnhubIndustry`), so
    when Finnhub is the primary source, downstream consumers like the market-
    context tool can't resolve the right sector ETF (e.g. Technology → XLK).
    yfinance's `info["sector"]` uses Yahoo's standard taxonomy that our
    SECTOR_ETF map keys on, so we lift it from the same `info` dict we're
    already fetching for analyst targets.

    Source: Yahoo Finance's Refinitiv consensus panel for the analyst block.
    Silent on failure — accuracy bonus, not load-bearing.
    """
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return result

    if not result.get("sector"):
        yf_sector = info.get("sector")
        if isinstance(yf_sector, str) and yf_sector:
            result["sector"] = yf_sector

    if not result.get("name"):
        yf_name = info.get("longName") or info.get("shortName")
        if isinstance(yf_name, str) and yf_name:
            result["name"] = yf_name

    tm = _to_float(info.get("targetMeanPrice"))
    th = _to_float(info.get("targetHighPrice"))
    tl = _to_float(info.get("targetLowPrice"))
    count_raw = info.get("numberOfAnalystOpinions")
    try:
        count = int(count_raw) if count_raw is not None else None
    except (TypeError, ValueError):
        count = None
    rm = _to_float(info.get("recommendationMean"))
    rk = info.get("recommendationKey")

    if tm is not None:
        result["analyst_target_mean"] = tm
    if th is not None:
        result["analyst_target_high"] = th
    if tl is not None:
        result["analyst_target_low"] = tl
    if count is not None:
        result["analyst_count"] = count
    if rm is not None:
        result["recommendation_mean"] = rm
    if isinstance(rk, str) and rk:
        result["recommendation_key"] = rk

    # General key stats — the same `info` dict carries TradingView's "Key stats".
    for field, info_key in (
        ("beta", "beta"),
        ("eps_ttm", "trailingEps"),
        ("dividend_yield", "dividendYield"),
        ("shares_float", "floatShares"),
        ("shares_outstanding", "sharesOutstanding"),
        ("net_income", "netIncomeToCommon"),
        ("total_revenue", "totalRevenue"),
        ("fifty_two_week_high", "fiftyTwoWeekHigh"),
        ("fifty_two_week_low", "fiftyTwoWeekLow"),
    ):
        val = _to_float(info.get(info_key))
        if val is not None:
            result[field] = val  # type: ignore[literal-required]

    # Company profile for the "About" card.
    summary = info.get("longBusinessSummary")
    if isinstance(summary, str) and summary.strip():
        result["description"] = summary.strip()
    if not result.get("website"):
        site = info.get("website")
        if isinstance(site, str) and site:
            result["website"] = site

    ceo = _extract_ceo(info.get("companyOfficers"))
    if ceo:
        result["ceo"] = ceo

    hq = _format_hq(info.get("city"), info.get("state"), info.get("country"))
    if hq:
        result["headquarters"] = hq

    employees = info.get("fullTimeEmployees")
    try:
        if employees is not None:
            result["employees"] = int(employees)
    except (TypeError, ValueError):
        pass

    return result


def _extract_ceo(officers: Any) -> str | None:
    """First officer whose title names them CEO. Names can carry stray double
    spaces from Yahoo, so collapse whitespace."""
    if not isinstance(officers, list):
        return None
    for off in officers:
        title = (off or {}).get("title") or ""
        if "CEO" in title or "Chief Executive" in title:
            name = (off or {}).get("name")
            if isinstance(name, str) and name.strip():
                return " ".join(name.split())
    return None


def _format_hq(city: Any, state: Any, country: Any) -> str | None:
    """'City, ST' for US companies (state present), else 'City, Country'."""
    if not isinstance(city, str) or not city:
        return None
    region = state if isinstance(state, str) and state else country
    if isinstance(region, str) and region:
        return f"{city}, {region}"
    return city


def get_fundamentals(ticker: str) -> Fundamentals:
    """Return company fundamentals for `ticker`, cached for 24h.

    Source priority:
      1. Finnhub (cleanest free data, 60 req/min, needs FINNHUB_API_KEY)
      2. yfinance (no key, decent quality, sometimes stale)
      3. Alpha Vantage (last resort: tight 25 calls/day, needs ALPHAVANTAGE_API_KEY)

    After the primary fetch, forward_pe is backfilled from yfinance if missing —
    Finnhub's free tier doesn't include real forward estimates.
    """
    key = ticker.upper()
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    result = _from_finnhub(ticker) or _from_yfinance(ticker) or _from_alphavantage(ticker)
    if result is None:
        raise ValueError(f"No fundamentals available for {ticker!r}")

    result = _backfill_forward_pe(result, ticker)
    result = _backfill_analyst_targets(result, ticker)
    result["days_until_earnings"] = _compute_days_until_earnings(result.get("earnings_date"))
    _cache[key] = (now, result)
    return result


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    snap = get_fundamentals(symbol)
    for key, value in snap.items():
        print(f"{key:18s} {value}")
