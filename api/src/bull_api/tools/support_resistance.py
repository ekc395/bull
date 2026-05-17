"""Pivot detection + clustering for support/resistance levels.

Algorithm:
  1. Find local extrema: ≥5 bars left + ≥2 bars right must be beaten.
     (Right-side window is relaxed near the recent end so today's swing
     high isn't permanently excluded — a 5/5 rule would mean the chart
     has "no resistance" until 5 bars after each new high.)
  2. Cluster pivots within ±1.5% of price to form levels.
  3. Return top-3 supports below current price and top-3 resistances above, ranked by touch count.
"""

from typing import TypedDict

import pandas as pd

PIVOT_WINDOW = 5
MIN_RIGHT = 2  # asymmetric: full window on left, at least this many bars on the right
CLUSTER_TOLERANCE = 0.015  # ±1.5% of cluster mean


class Level(TypedDict):
    price: float
    touch_count: int
    last_touch_date: str


class SupportResistance(TypedDict):
    support: list[Level]
    resistance: list[Level]


def _find_pivots(series: pd.Series, *, is_high: bool, window: int = PIVOT_WINDOW, min_right: int = MIN_RIGHT) -> list[tuple[float, pd.Timestamp]]:
    """Local extrema with `window` bars on the left and ≥`min_right` on the right.

    The right-side window shrinks near the end of the series so recent swing
    highs/lows still qualify as pivots (a strict 5/5 rule would discard the
    most relevant levels for a stock making new highs). Returns [(price, date)].
    """
    values = series.to_numpy()
    pivots: list[tuple[float, pd.Timestamp]] = []
    n = len(values)
    for i in range(window, n - min_right):
        v = values[i]
        left = values[i - window : i]
        right_size = min(window, n - 1 - i)
        right = values[i + 1 : i + 1 + right_size]
        if is_high:
            if v > left.max() and v > right.max():
                pivots.append((float(v), series.index[i]))
        else:
            if v < left.min() and v < right.min():
                pivots.append((float(v), series.index[i]))
    return pivots


def _cluster(pivots: list[tuple[float, pd.Timestamp]], tolerance: float = CLUSTER_TOLERANCE) -> list[list[tuple[float, pd.Timestamp]]]:
    """Greedy 1D clustering: merge a pivot into the running cluster if its price
    is within ±tolerance of the running mean; otherwise start a new cluster.
    """
    if not pivots:
        return []
    sorted_pivots = sorted(pivots, key=lambda p: p[0])
    clusters: list[list[tuple[float, pd.Timestamp]]] = []
    current = [sorted_pivots[0]]
    for p in sorted_pivots[1:]:
        mean = sum(x[0] for x in current) / len(current)
        if abs(p[0] - mean) / mean <= tolerance:
            current.append(p)
        else:
            clusters.append(current)
            current = [p]
    clusters.append(current)
    return clusters


def find_support_resistance(prices: pd.DataFrame) -> SupportResistance:
    """Cluster confirmed pivot highs+lows into levels, split by current price."""
    min_rows = 2 * PIVOT_WINDOW + 1
    if len(prices) < min_rows:
        return {"support": [], "resistance": []}

    high_pivots = _find_pivots(prices["High"], is_high=True)
    low_pivots = _find_pivots(prices["Low"], is_high=False)
    current_price = float(prices["Close"].iloc[-1])

    levels: list[Level] = []
    for cluster in _cluster(high_pivots + low_pivots):
        avg = sum(p[0] for p in cluster) / len(cluster)
        last = max(p[1] for p in cluster)
        levels.append(
            {
                "price": round(avg, 2),
                "touch_count": len(cluster),
                "last_touch_date": last.strftime("%Y-%m-%d"),
            }
        )

    # Most-touched first; on ties, prefer the level closest to current price (most actionable).
    support = sorted(
        [lvl for lvl in levels if lvl["price"] < current_price],
        key=lambda x: (-x["touch_count"], -x["price"]),
    )[:3]
    resistance = sorted(
        [lvl for lvl in levels if lvl["price"] >= current_price],
        key=lambda x: (-x["touch_count"], x["price"]),
    )[:3]

    return {"support": support, "resistance": resistance}


if __name__ == "__main__":
    import sys

    from .prices import get_price_history

    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    frame = get_price_history(symbol)
    sr = find_support_resistance(frame)
    current = float(frame["Close"].iloc[-1])
    print(f"{symbol}  current ${current:.2f}")
    print("resistance (above):")
    for lvl in sr["resistance"]:
        print(f"  ${lvl['price']:>8.2f}  touches={lvl['touch_count']}  last={lvl['last_touch_date']}")
    print("support (below):")
    for lvl in sr["support"]:
        print(f"  ${lvl['price']:>8.2f}  touches={lvl['touch_count']}  last={lvl['last_touch_date']}")
