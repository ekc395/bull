"""`broker.alpaca.place_order` amount validation (money path).

The notional/qty checks run BEFORE `_client()`, so these raise without any
network or credentials. Guards a manual-override zero/negative from reaching
Alpaca as an opaque error.
"""

import pytest

from bull_api.broker.alpaca import place_order


def test_place_order_rejects_both_amounts():
    with pytest.raises(ValueError, match="exactly one"):
        place_order("AAPL", "buy", notional=100, qty=1)


def test_place_order_rejects_no_amount():
    with pytest.raises(ValueError, match="exactly one"):
        place_order("AAPL", "buy")


@pytest.mark.parametrize("notional", [0, -5])
def test_place_order_rejects_nonpositive_notional(notional):
    with pytest.raises(ValueError, match="notional must be positive"):
        place_order("AAPL", "buy", notional=notional)


@pytest.mark.parametrize("qty", [0, -1])
def test_place_order_rejects_nonpositive_qty(qty):
    with pytest.raises(ValueError, match="qty must be positive"):
        place_order("AAPL", "buy", qty=qty)
