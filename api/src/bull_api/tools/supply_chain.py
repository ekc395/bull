"""Supply-chain context for a ticker.

- `data/supply_chain.yaml` holds a curated map for well-known tickers (NVDA → TSMC, etc.).
- For tickers not in the yaml, queries Google News RSS for "{company} suppliers/customers".
- 7d TTL cache.
"""

from typing import TypedDict


class SupplyChainContext(TypedDict):
    suppliers: list[str]
    customers: list[str]
    dependencies: list[str]
    notes: list[str]


def get_supply_chain_context(ticker: str) -> SupplyChainContext:
    raise NotImplementedError
