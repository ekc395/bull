"""News: yfinance .news + Google News RSS via feedparser. 6h TTL cache.

Free — no paid Anthropic web_search.
"""

from typing import TypedDict


class NewsItem(TypedDict):
    title: str
    source: str
    url: str
    published_at: str
    summary: str


def get_recent_news(ticker: str, days: int = 7) -> list[NewsItem]:
    raise NotImplementedError
