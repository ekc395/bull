"""Phase 4 — outcome-conditioned recall block.

Pure helpers only (no DB): the action-independent setup signature, similarity
ranking with the same-ticker boost, and the token-capped block formatting.
"""

from datetime import datetime, timezone

from bull_api.policy.recall import (
    MAX_BLOCK_CHARS,
    RecallRow,
    _format_block,
    _rank,
    _setup_signature,
    _similarity,
)


def _facts(**ind):
    base_ind = {"sma_50": 95.0, "sma_200": 90.0}
    base_ind.update(ind)
    return {
        "indicators": base_ind,
        "market_context": {
            "spy": {"above_sma_50": True},
            "sector": {"above_sma_50": True},
            "vix_state": "calm",
        },
        "fundamentals": {"days_until_earnings": 40},
    }


def _row(ticker="AAPL", *, setup, ret=2.0, conf=70, action="BUY", day=1) -> RecallRow:
    return RecallRow(
        ticker=ticker,
        created_at=datetime(2026, 5, day, tzinfo=timezone.utc),
        action=action,
        confidence=conf,
        horizon_days=20,
        return_pct=ret,
        setup=setup,
    )


# --- setup signature -------------------------------------------------------


def test_setup_signature_is_action_independent():
    # No action passed, yet the trend stack (action-independent) is populated.
    sig = _setup_signature(_facts())
    assert sig["trend_stack_up"] is True  # sma50 > sma200
    assert sig["market_above_sma_50"] is True
    assert sig["sector_above_sma_50"] is True
    assert sig["vix_state"] == "calm"
    assert sig["earnings_window"] is False


def test_setup_signature_earnings_window():
    sig = _setup_signature(_facts())  # 40d out
    assert sig["earnings_window"] is False
    near = _facts()
    near["fundamentals"]["days_until_earnings"] = 3
    assert _setup_signature(near)["earnings_window"] is True


def test_setup_signature_empty_bundle():
    sig = _setup_signature({})
    assert sig["trend_stack_up"] is None
    assert sig["earnings_window"] is False


# --- similarity & ranking --------------------------------------------------


def test_similarity_counts_matching_dims():
    target = _setup_signature(_facts())
    same = dict(target)
    assert _similarity(target, same, same_ticker=False) == len(
        [v for v in target.values() if v is not None]
    )


def test_similarity_same_ticker_boost():
    target = _setup_signature(_facts())
    other = {k: None for k in target}  # zero dimension matches
    assert _similarity(target, other, same_ticker=False) == 0
    assert _similarity(target, other, same_ticker=True) == 2


def test_rank_prefers_more_similar_then_recent():
    target = _setup_signature(_facts())
    match = dict(target)
    nomatch = {k: None for k in target}
    rows = [
        _row("XYZ", setup=nomatch, day=9),  # recent but dissimilar
        _row("DEF", setup=match, day=1),  # older but fully similar
    ]
    ranked = _rank(target, rows, ticker="AAPL", k=5)
    assert ranked[0].ticker == "DEF"


def test_rank_same_ticker_wins_ties():
    target = _setup_signature(_facts())
    nomatch = {k: None for k in target}
    rows = [
        _row("OTHER", setup=nomatch, day=5),
        _row("AAPL", setup=nomatch, day=1),  # same ticker → +2 boost
    ]
    ranked = _rank(target, rows, ticker="AAPL", k=5)
    assert ranked[0].ticker == "AAPL"


# --- formatting ------------------------------------------------------------


def test_format_block_empty():
    assert _format_block("AAPL", [], MAX_BLOCK_CHARS) == ""


def test_format_block_renders_signed_returns():
    sig = _setup_signature(_facts())
    rows = [
        _row("AAPL", setup=sig, ret=3.4, conf=72, action="BUY"),
        _row("NVDA", setup=sig, ret=-2.1, conf=66, action="SELL"),
    ]
    block = _format_block("AAPL", rows, MAX_BLOCK_CHARS)
    assert "PRIOR CALLS" in block
    assert "AAPL 2026-05-01: BUY @conf 72 → +3.4% realized over 20d" in block
    assert "NVDA 2026-05-01: SELL @conf 66 → -2.1% realized over 20d" in block


def test_format_block_respects_char_cap():
    sig = _setup_signature(_facts())
    rows = [_row(f"T{i:03d}", setup=sig, day=(i % 27) + 1) for i in range(50)]
    block = _format_block("AAPL", rows, max_chars=300)
    assert len(block) <= 300 + 80  # header + at least one line tolerance
    assert block.count("\n") < 50  # trimmed
