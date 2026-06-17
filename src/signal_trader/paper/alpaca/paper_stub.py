"""Thin Alpaca paper-trading stub (alpaca-py 0.43.4).

Phase 1 scope: push exactly one paper market order to prove the plumbing
(Spec §5.7). Always paper=True; keys come from .env via config, never
hard-coded. Full order routing / PnL is Phase 3. In tests TradingClient is
mocked — no live call ever.
"""
from __future__ import annotations

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


class AlpacaPaperStub:
    def __init__(self, api_key: str | None, secret_key: str | None):
        if not api_key or not secret_key:
            raise ValueError("Alpaca API key and secret required (set them in .env)")
        self._client = TradingClient(api_key, secret_key, paper=True)

    def submit_market_buy(self, symbol: str, qty: int = 1) -> str:
        """Submit a single paper day-order market buy; return the order id."""
        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        order = self._client.submit_order(order_data=request)
        return str(order.id)
