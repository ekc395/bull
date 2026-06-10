"""Deterministic short-mode entry strategies (the tournament roster).

Adding a strategy = one new module exposing `NAME` + `evaluate(facts)` and a
line here. Removing a loser after the backtest settles the tournament is the
reverse. `REGISTRY` preserves insertion order (dict) — the UI lists them in
this order.
"""

from . import bounce, breakout, pullback
from .base import (
    LLM_SHADE_BAND,
    MAX_HOLD_TRADING_DAYS,
    StrategyDecision,
    StrategyFn,
    enforce_llm_review,
)

REGISTRY: dict[str, StrategyFn] = {
    pullback.NAME: pullback.evaluate,
    breakout.NAME: breakout.evaluate,
    bounce.NAME: bounce.evaluate,
}

__all__ = [
    "LLM_SHADE_BAND",
    "MAX_HOLD_TRADING_DAYS",
    "REGISTRY",
    "StrategyDecision",
    "StrategyFn",
    "enforce_llm_review",
]
