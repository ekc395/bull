"""Supply-chain context for a ticker.

- `data/supply_chain.yaml` holds a curated map for well-known tickers (NVDA → TSMC, etc.).
- For tickers not in the yaml, queries Google News RSS for "{ticker} suppliers/customers".
- 7d TTL cache.
"""

import time
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import quote_plus

import feedparser
import yaml


class SupplyChainContext(TypedDict):
    suppliers: list[str]
    customers: list[str]
    dependencies: list[str]
    notes: list[str]


_TTL_SECONDS = 7 * 24 * 60 * 60
_cache: dict[str, tuple[float, SupplyChainContext]] = {}

_YAML_PATH = Path(__file__).parent / "data" / "supply_chain.yaml"
_yaml_data: dict[str, Any] | None = None


def _load_yaml() -> dict[str, Any]:
    global _yaml_data
    if _yaml_data is None:
        with _YAML_PATH.open() as f:
            _yaml_data = yaml.safe_load(f) or {}
    return _yaml_data


def _from_rss(ticker: str) -> SupplyChainContext:
    """Fallback for tickers not in the yaml: scrape headline snippets from
    Google News for supplier/customer mentions. Returns notes only — RSS
    can't reliably populate structured supplier/customer lists.
    """
    notes: list[str] = []
    for query in (f"{ticker} suppliers", f"{ticker} customers"):
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries[:5]:
            title = entry.get("title") or ""
            if title:
                notes.append(title)
    return {"suppliers": [], "customers": [], "dependencies": [], "notes": notes[:10]}


def get_supply_chain_context(ticker: str) -> SupplyChainContext:
    key = ticker.upper()
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    data = _load_yaml()
    entry = data.get(key)
    if entry:
        result: SupplyChainContext = {
            "suppliers": entry.get("suppliers") or [],
            "customers": entry.get("customers") or [],
            "dependencies": entry.get("dependencies") or [],
            "notes": entry.get("notes") or [],
        }
    else:
        result = _from_rss(ticker)

    _cache[key] = (now, result)
    return result


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    sc = get_supply_chain_context(symbol)
    for k, v in sc.items():
        print(f"{k}:")
        for item in v:
            print(f"  - {item}")
