"""Broker seam: vendor-neutral paper-trading interface (analogous to PriceProvider).

The paper loop depends only on this Protocol, never on alpaca-py directly, so
the whole lifecycle is testable offline with a fake. Fill carries the ACTUAL
filled price and time the broker reports — we log what really happened, never an
idealized fill (Spec §8.1). A live alpaca-py adapter conforming to Broker is the
controller-only piece gated on paper API keys.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    qty: float
    price: float
    filled_at: dt.datetime
    side: str  # "buy" | "sell"


@runtime_checkable
class Broker(Protocol):
    def submit_market_buy(self, symbol: str, qty: float) -> Fill:
        """Submit a paper market buy and return the resulting fill."""
        ...

    def submit_market_sell(self, symbol: str, qty: float) -> Fill:
        """Submit a paper market sell and return the resulting fill."""
        ...
