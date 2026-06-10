"""Deterministic short-mode entry strategies (the tournament roster).

Adding a strategy = one new module exposing `NAME` + `evaluate(facts)` and a
line here. Removing a loser after the backtest settles the tournament is the
reverse. `REGISTRY` preserves insertion order (dict) — the UI lists them in
this order.
"""

from . import connors, pullback, turtle
from .base import (
    LLM_SHADE_BAND,
    MAX_HOLD_TRADING_DAYS,
    StrategyDecision,
    StrategyFn,
    enforce_llm_review,
)

# Pruned after the 2026-06 Dow-30 regime-split tournament (see plan.md and git
# history): breakout-v1 and wyckoff-spring-v1 flipped sign across regimes,
# bounce-v1 was a coin flip in both. Their evaluations remain in old verdicts'
# algo_json and still aggregate in scores summaries.
REGISTRY: dict[str, StrategyFn] = {
    pullback.NAME: pullback.evaluate,
    connors.NAME: connors.evaluate,
    turtle.NAME: turtle.evaluate,
}

__all__ = [
    "LLM_SHADE_BAND",
    "MAX_HOLD_TRADING_DAYS",
    "REGISTRY",
    "StrategyDecision",
    "StrategyFn",
    "enforce_llm_review",
]
