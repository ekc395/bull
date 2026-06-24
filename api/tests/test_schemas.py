"""Request-schema validation — the paid-call and money-path entry points.

`AnalyzeRequest.ticker` is the string that reaches the prompt + yfinance, so it
is bounded and character-restricted. `ExecuteOrderRequest` guards the order
amount. Both are pure Pydantic — no DB/network.
"""

import pytest
from pydantic import ValidationError

from bull_api.schemas import AnalyzeRequest, ExecuteOrderRequest


# --- AnalyzeRequest --------------------------------------------------------


def test_analyze_request_accepts_plain_ticker():
    r = AnalyzeRequest(ticker="AAPL")
    assert r.ticker == "AAPL"
    assert r.force is False
    assert r.timeframe == "short"


def test_analyze_request_accepts_dotted_ticker():
    # Class-share tickers carry a dot; the pattern must allow it.
    assert AnalyzeRequest(ticker="BRK.B").ticker == "BRK.B"


def test_analyze_request_rejects_empty():
    with pytest.raises(ValidationError):
        AnalyzeRequest(ticker="")


def test_analyze_request_rejects_too_long():
    with pytest.raises(ValidationError):
        AnalyzeRequest(ticker="A" * 17)


@pytest.mark.parametrize("bad", ["AA PL", "AA;PL", "AA/PL", "<script>", "AA$", "AA*"])
def test_analyze_request_rejects_bad_chars(bad):
    with pytest.raises(ValidationError):
        AnalyzeRequest(ticker=bad)


# --- ExecuteOrderRequest ---------------------------------------------------


def test_execute_order_allows_single_amount():
    assert ExecuteOrderRequest(verdict_id=1, qty=2).qty == 2
    assert ExecuteOrderRequest(verdict_id=1, notional=50).notional == 50


def test_execute_order_allows_no_amount():
    # No amount → the policy gate sizes it server-side.
    r = ExecuteOrderRequest(verdict_id=1)
    assert r.notional is None and r.qty is None


def test_execute_order_rejects_both_amounts():
    with pytest.raises(ValidationError):
        ExecuteOrderRequest(verdict_id=1, notional=100, qty=1)


@pytest.mark.parametrize("amount", [{"notional": 0}, {"notional": -5}, {"qty": 0}, {"qty": -1}])
def test_execute_order_rejects_nonpositive(amount):
    with pytest.raises(ValidationError):
        ExecuteOrderRequest(verdict_id=1, **amount)
