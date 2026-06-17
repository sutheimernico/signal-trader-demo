"""Shared cost model: flat per-trade commission + slippage, as fractions.

One tested unit feeds BOTH engines and the benchmark, so 'after costs'
means the same thing everywhere (Acceptance criterion §8.6). Both values
are per-side fractions of notional. backtesting.py's `commission` is also a
per-side fraction; vectorbt's `fees`/`slippage` are per-side fractions too,
so this maps directly onto both engines.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_per_trade: float
    slippage: float

    def __post_init__(self) -> None:
        if self.commission_per_trade < 0:
            raise ValueError("commission_per_trade must be >= 0")
        if self.slippage < 0:
            raise ValueError("slippage must be >= 0")

    def round_trip_fraction(self) -> float:
        """Fraction lost on a full buy+sell round trip (both legs)."""
        return 2 * (self.commission_per_trade + self.slippage)

    def fill_price(self, mid_price: float, side: str) -> float:
        """Slippage-adjusted fill: buys fill higher, sells lower.

        Reference helper for manual cost reasoning (e.g. break-even analysis).
        Neither engine calls this — each applies costs via its own API
        (backtesting.py ``spread``, vectorbt ``fees``/``slippage``).
        """
        if side == "buy":
            return mid_price * (1 + self.slippage)
        if side == "sell":
            return mid_price * (1 - self.slippage)
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
