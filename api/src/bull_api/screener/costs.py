"""Single source of truth for the model-cost rule-of-thumb used in scan estimates.

Numbers are from `CLAUDE.md` Gotchas + observed token usage in production. The
estimate is intentionally rough — it sizes the user's confirmation prompt, not
their bill.
"""

PER_ANALYSIS_USD: dict[str, float] = {
    "claude-opus-4-7": 0.12,
    "claude-sonnet-4-6": 0.025,
    "claude-haiku-4-5-20251001": 0.008,
}

DEFAULT_USD = 0.12


def estimate_scan_cost_usd(num_candidates: int, model: str) -> float:
    return round(num_candidates * PER_ANALYSIS_USD.get(model, DEFAULT_USD), 2)
