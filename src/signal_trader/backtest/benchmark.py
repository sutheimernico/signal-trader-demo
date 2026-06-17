"""Buy-and-hold benchmark, charged the SAME costs as the strategy.

Acceptance §8.6: performance is always measured against a benchmark after
costs. We buy once at the first bar (paying entry commission + slippage)
and hold; equity is share count times close thereafter.
"""
from __future__ import annotations

import pandas as pd

from signal_trader.backtest.costs import CostModel


def buy_and_hold_equity(
    close: pd.Series, cost_model: CostModel, init_cash: float = 10_000.0
) -> pd.Series:
    """Post-cost equity curve of buying the asset on bar 0 and holding.

    Commission is charged on the invested notional (matching how both engines
    charge it: backtesting.py ``commission`` and vectorbt ``fees`` are per-side
    fractions of traded notional), not on gross ``init_cash``. The held
    position pays no exit cost — the intentional asymmetry of a passive hold.
    """
    entry_price = cost_model.fill_price(float(close.iloc[0]), side="buy")
    shares = init_cash / (entry_price * (1 + cost_model.commission_per_trade))
    equity = shares * close
    equity.index = close.index
    return equity
