"""Supply-chain context for a ticker.

- `data/supply_chain.yaml` holds a curated override map for tickers where we
  don't want to rely on model recall (recent IPOs, ticker collisions, pivots).
- For tickers not in the yaml, returns an empty bundle. The synthesis prompt
  authorizes the model to fill structural facts (suppliers, customers,
  geopolitical/market-structure dependencies) from its own training knowledge.
- 7d TTL cache.
"""

import time
from pathlib import Path
from typing import Any, TypedDict

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
        try:
            with _YAML_PATH.open() as f:
                _yaml_data = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            # Override file is optional/empty by default — a missing or malformed
            # file must not crash an analysis. Fall back to no overrides.
            _yaml_data = {}
    return _yaml_data


_EMPTY: SupplyChainContext = {
    "suppliers": [],
    "customers": [],
    "dependencies": [],
    "notes": [],
}


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
        result = dict(_EMPTY)  # type: ignore[assignment]

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
