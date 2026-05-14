"""Pivot detection + clustering for support/resistance levels.

Algorithm:
  1. Find local extrema (5-bar confirmation: high/low must beat ±5 bars).
  2. Cluster pivots within ±1.5% of price to form levels.
  3. Return top-3 supports below current price and top-3 resistances above, ranked by touch count.
"""

from typing import TypedDict

import pandas as pd


class Level(TypedDict):
    price: float
    touch_count: int
    last_touch_date: str


class SupportResistance(TypedDict):
    support: list[Level]
    resistance: list[Level]


def find_support_resistance(prices: pd.DataFrame) -> SupportResistance:
    raise NotImplementedError
