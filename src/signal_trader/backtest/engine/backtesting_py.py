"""Event-driven adapter over backtesting.py 0.6.5.

Same momentum signal as the vectorbt adapter, but with realistic next-bar
fills, so the report can show event-driven trailing vectorized. Costs:
backtesting.py's `commission` (per-side fraction) carries our commission;
slippage is folded into `spread` (a per-trade relative bid-ask cost).

Signal semantics: momentum_signals returns state-based boolean series (True
on every bar the condition holds, shifted one bar to prevent same-bar
lookahead). The `next()` guards — "not self.position" on entry, "self.position"
on exit — prevent re-entering on every True bar; fills occur on the bar
AFTER the signal fires (backtesting.py default: fill on next open), so there
is no same-bar lookahead.
"""
from __future__ import annotations

import pandas as pd
from backtesting import Backtest, Strategy

from signal_trader.backtest.baselines.momentum import momentum_signals
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.result import BacktestResult

_INIT_CASH = 10_000


def _make_strategy(lookback: int) -> type[Strategy]:
    class _Momentum(Strategy):
        def init(self):
            close = pd.Series(self.data.Close, index=self.data.index)
            entries, exits = momentum_signals(close, lookback=lookback)
            self.entries = self.I(lambda: entries.to_numpy(), name="entries")
            self.exits = self.I(lambda: exits.to_numpy(), name="exits")

        def next(self):
            # State-based signals: guard on position to trade only at transitions.
            if self.entries[-1] and not self.position:
                self.buy()
            elif self.exits[-1] and self.position:
                self.position.close()

    return _Momentum


class BacktestingPyAdapter:
    def __init__(self, cost_model: CostModel):
        self.cost_model = cost_model

    def run(self, ohlcv: pd.DataFrame, lookback: int = 50) -> BacktestResult:
        bt = Backtest(
            ohlcv,
            _make_strategy(lookback),
            cash=_INIT_CASH,
            commission=self.cost_model.commission_per_trade,
            spread=self.cost_model.slippage,
            finalize_trades=True,
        )
        stats = bt.run()
        equity = stats["_equity_curve"]["Equity"]
        equity.index = pd.DatetimeIndex(ohlcv.index)
        return BacktestResult(
            engine="backtesting.py",
            equity_curve=equity,
            n_trades=int(stats["# Trades"]),
        )
