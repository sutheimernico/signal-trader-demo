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
    """Post-cost equity curve of buying the asset on bar 0 and holding."""
    entry_price = cost_model.fill_price(float(close.iloc[0]), side="buy")
    commission_cash = init_cash * cost_model.commission_per_trade
    investable = init_cash - commission_cash
    shares = investable / entry_price
    equity = shares * close
    equity.index = close.index
    return equity
