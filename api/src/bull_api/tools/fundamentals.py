"""Fundamentals: yfinance .info primary; Alpha Vantage OVERVIEW fallback. 24h TTL cache."""

from typing import TypedDict


class Fundamentals(TypedDict, total=False):
    sector: str
    industry: str
    market_cap: float
    trailing_pe: float | None
    forward_pe: float | None
    profit_margins: float | None
    revenue_growth: float | None
    earnings_date: str | None


def get_fundamentals(ticker: str) -> Fundamentals:
    raise NotImplementedError
