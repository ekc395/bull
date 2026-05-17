"""News: Finnhub + yfinance + Google News RSS, deduped. 6h TTL cache.

Free — no paid Anthropic web_search. Triple-sourced for accuracy:
  - Finnhub /company-news is ticker-tagged and multi-publisher (primary).
  - yfinance .news is Yahoo's curated feed (secondary).
  - Google News RSS is broad coverage (tertiary).
Items are deduped by normalized title; the best-ranked publisher wins.
"""

import time
from datetime import UTC, date, datetime, timedelta
from typing import TypedDict
from urllib.parse import quote_plus

import feedparser
import httpx
import yfinance as yf

from ..config import settings


class NewsItem(TypedDict):
    title: str
    source: str
    url: str
    published_at: str  # ISO 8601 when known
    summary: str


_TTL_SECONDS = 6 * 60 * 60
_cache: dict[str, tuple[float, list[NewsItem]]] = {}

# Trusted-publisher whitelist (lowercase substring match). Lower index = more authoritative.
# Used to pick the winner when the same story shows up via multiple sources.
_TRUSTED_SOURCES = [
    "reuters",
    "bloomberg",
    "wall street journal",
    "wsj",
    "financial times",
    "ft.com",
    "associated press",
    "ap news",
    "cnbc",
    "marketwatch",
    "barron",
    "yahoo finance",
    "nytimes",
    "the new york times",
    "investor's business daily",
]


def _source_rank(source: str) -> int:
    s = (source or "").lower().strip()
    for i, trusted in enumerate(_TRUSTED_SOURCES):
        if trusted in s:
            return i
    return 999


def _normalize_title(t: str) -> str:
    return (t or "").lower().strip()[:60]


def _from_finnhub(ticker: str, days: int) -> list[NewsItem]:
    if not settings.finnhub_api_key:
        return []
    today = date.today()
    from_date = today - timedelta(days=days)
    try:
        with httpx.Client(timeout=10.0) as client:
            data = client.get(
                "https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": ticker,
                    "from": from_date.isoformat(),
                    "to": today.isoformat(),
                    "token": settings.finnhub_api_key,
                },
            ).json()
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    items: list[NewsItem] = []
    for entry in data:
        ts = entry.get("datetime")
        published = ""
        if ts:
            try:
                published = datetime.fromtimestamp(int(ts), tz=UTC).isoformat()
            except (TypeError, ValueError, OSError):
                pass
        items.append(
            {
                "title": entry.get("headline") or "",
                "source": entry.get("source") or "",
                "url": entry.get("url") or "",
                "published_at": published,
                "summary": entry.get("summary") or "",
            }
        )
    return items


def _from_yfinance(ticker: str) -> list[NewsItem]:
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    items: list[NewsItem] = []
    for entry in raw:
        # yfinance's news schema changed: newer versions nest under "content".
        content = entry.get("content") or entry
        url = ""
        canonical = content.get("canonicalUrl")
        if isinstance(canonical, dict):
            url = canonical.get("url") or ""
        url = url or content.get("link") or ""

        provider = content.get("provider")
        publisher = ""
        if isinstance(provider, dict):
            publisher = provider.get("displayName") or ""
        publisher = publisher or content.get("publisher") or ""

        items.append(
            {
                "title": content.get("title") or "",
                "source": publisher,
                "url": url,
                "published_at": content.get("pubDate") or "",
                "summary": content.get("summary") or "",
            }
        )
    return items


def _from_google_news(ticker: str) -> list[NewsItem]:
    q = quote_plus(f"{ticker} stock")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []
    items: list[NewsItem] = []
    for entry in feed.entries[:30]:
        title = entry.get("title") or ""
        # Google News titles are "Article Title - Publisher Name"
        if " - " in title:
            article_title, source = title.rsplit(" - ", 1)
        else:
            article_title, source = title, "google news"
        items.append(
            {
                "title": article_title.strip(),
                "source": source.strip(),
                "url": entry.get("link") or "",
                "published_at": entry.get("published") or "",
                "summary": entry.get("summary") or "",
            }
        )
    return items


def get_recent_news(ticker: str, days: int = 7) -> list[NewsItem]:
    """Combined news feed from Finnhub + yfinance + Google News, deduped by title."""
    cache_key = f"{ticker.upper()}:{days}"
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    all_items = _from_finnhub(ticker, days) + _from_yfinance(ticker) + _from_google_news(ticker)

    # Dedupe by normalized title; keep the entry from the most trusted publisher.
    by_title: dict[str, NewsItem] = {}
    for item in all_items:
        if not item["title"]:
            continue
        key = _normalize_title(item["title"])
        existing = by_title.get(key)
        if existing is None or _source_rank(item["source"]) < _source_rank(existing["source"]):
            by_title[key] = item

    # Newest first; entries without a date go to the end.
    result = sorted(by_title.values(), key=lambda x: x["published_at"] or "", reverse=True)
    result = result[:20]

    _cache[cache_key] = (now, result)
    return result


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    news = get_recent_news(symbol)
    print(f"{symbol}: {len(news)} articles after dedupe\n")
    for n in news[:10]:
        print(f"[{n['source'][:24]:24s}] {n['title'][:80]}")
        print(f"  {n['published_at'][:25]}  {n['url'][:80]}")
