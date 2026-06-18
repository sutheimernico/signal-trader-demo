"""Live Alpaca paper broker conforming to the Broker seam (alpaca-py 0.43.4).

Submits paper market orders and returns the ACTUAL fill (filled_avg_price /
filled_at the broker reports) — never a fabricated price (Spec §8.1). Market
orders fill near-instantly in Alpaca paper, but the submit response is often not
yet filled, so we poll get_order_by_id until a fill price appears; if none
appears we RAISE rather than invent a number. Always paper=True; keys via .env.

Controller-only at runtime: needs paper API keys. In tests TradingClient is
mocked and `sleep` is injected as a no-op — no live call, no real wait.
"""
from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from signal_trader.paper.broker import Fill


def _to_datetime(value: object) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return dt.datetime.fromisoformat(text)


class AlpacaPaperBroker:
    def __init__(
        self,
        api_key: str | None,
        secret_key: str | None,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = 0.5,
        max_poll_attempts: int = 10,
    ):
        if not api_key or not secret_key:
            raise ValueError("Alpaca API key and secret required (set them in .env)")
        self._client = TradingClient(api_key, secret_key, paper=True)
        self._sleep = sleep
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts

    def submit_market_buy(self, symbol: str, qty: float) -> Fill:
        return self._submit(symbol, qty, OrderSide.BUY, "buy")

    def submit_market_sell(self, symbol: str, qty: float) -> Fill:
        return self._submit(symbol, qty, OrderSide.SELL, "sell")

    def _submit(self, symbol: str, qty: float, side: OrderSide, label: str) -> Fill:
        request = MarketOrderRequest(
            symbol=symbol, qty=qty, side=side, time_in_force=TimeInForce.DAY
        )
        order = self._client.submit_order(order_data=request)
        filled = self._await_fill(order)
        return Fill(
            order_id=str(filled.id),
            symbol=str(filled.symbol or symbol),
            qty=float(filled.qty or qty),
            price=float(filled.filled_avg_price),
            filled_at=_to_datetime(filled.filled_at),
            side=label,
        )

    def _await_fill(self, order):
        current = order
        for _ in range(self._max_poll_attempts):
            if current.filled_avg_price is not None:
                return current
            self._sleep(self._poll_interval)
            current = self._client.get_order_by_id(order.id)
        raise ValueError(
            f"order {order.id} not filled after {self._max_poll_attempts} polls"
        )
