"""Vectorized adapter over vectorbt 1.0.0.

Same momentum entries/exits as the event-driven adapter. fees/slippage are
per-side fractions (map directly from CostModel). freq='1D' so vectorbt can
annualize. The equity curve here is `pf.value()` — note it does NOT model
next-bar-open fills, which is exactly why the report shows it looking
better than the event-driven run on identical signals.
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt

from signal_trader.backtest.baselines.momentum import momentum_signals
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.result import BacktestResult

_INIT_CASH = 10_000


class VectorbtAdapter:
    def __init__(self, cost_model: CostModel):
        self.cost_model = cost_model

    def run(self, close: pd.Series, lookback: int = 50) -> BacktestResult:
        entries, exits = momentum_signals(close, lookback=lookback)
        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            init_cash=_INIT_CASH,
            fees=self.cost_model.commission_per_trade,
            slippage=self.cost_model.slippage,
            freq="1D",
        )
        equity = pf.value()
        equity.index = pd.DatetimeIndex(close.index)
        return BacktestResult(
            engine="vectorbt",
            equity_curve=equity,
            n_trades=int(pf.trades.count()),
        )
