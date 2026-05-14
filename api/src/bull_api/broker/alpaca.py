"""Alpaca paper-trading wrapper.

CRITICAL: `paper=True` is hardcoded. Never construct a live TradingClient.
"""

from typing import TypedDict


class AlpacaAccount(TypedDict):
    equity: float
    cash: float
    buying_power: float


class AlpacaPosition(TypedDict):
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float


def get_account() -> AlpacaAccount:
    raise NotImplementedError


def get_positions() -> list[AlpacaPosition]:
    raise NotImplementedError


def place_order(symbol: str, side: str, notional: float) -> dict:
    """Market order, DAY TIF. notional = dollars to deploy. Always paper."""
    raise NotImplementedError


def close_position(symbol: str) -> dict:
    raise NotImplementedError


def get_recent_orders(limit: int = 50) -> list[dict]:
    raise NotImplementedError
