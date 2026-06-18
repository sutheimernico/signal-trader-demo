"""Insider long-term strategy: consolidated signals -> PIT entries/exits.

Both Phase-1 engines consume boolean entries/exits aligned to the close index.
Point-in-time: an entry fires on the FIRST bar STRICTLY AFTER timestamp_known
(the filing is public only from the known date; the earliest tradable bar is
the next session). Exit fires `hold_bars` bars after entry — a fixed holding
period, the simplest rule that exercises the harness. No same-bar fills, so the
Phase-1 shift-test stays meaningful.
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt
from backtesting import Backtest, Strategy

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.result import BacktestResult
from signal_trader.store.signal_store import StoredSignal

_INIT_CASH = 10_000


def insider_entries_exits(
    close: pd.Series,
    signals: list[StoredSignal],
    hold_bars: int = 5,
) -> tuple[pd.Series, pd.Series]:
    """Boolean (entries, exits) aligned to `close` for the given signals."""
    entries = pd.Series(False, index=close.index)
    exits = pd.Series(False, index=close.index)
    for sig in signals:
        after = close.index[close.index > pd.Timestamp(sig.timestamp_known)]
        if len(after) == 0:
            continue
        entry_ts = after[0]
        entry_pos = close.index.get_loc(entry_ts)
        entries.iloc[entry_pos] = True
        exit_pos = entry_pos + hold_bars
        if exit_pos < len(close):
            exits.iloc[exit_pos] = True
    return entries, exits


def _make_signal_strategy(entries: pd.Series, exits: pd.Series) -> type[Strategy]:
    class _Signal(Strategy):
        def init(self):
            self.entries = self.I(lambda: entries.to_numpy(), name="entries")
            self.exits = self.I(lambda: exits.to_numpy(), name="exits")

        def next(self):
            if self.entries[-1] and not self.position:
                self.buy()
            elif self.exits[-1] and self.position:
                self.position.close()

    return _Signal


def run_insider_through_engines(
    close: pd.Series,
    signals: list[StoredSignal],
    cost_model: CostModel,
    hold_bars: int = 5,
) -> dict[str, BacktestResult]:
    """Run the insider entries/exits through BOTH Phase-1 engines after costs.

    Known fill-timing asymmetry (same as the Phase-1 momentum report): vectorbt's
    from_signals fills on the signal bar, backtesting.py fills next-bar-open. Both
    consume PIT-safe entries (already placed strictly after the filing date), so
    neither leaks; but vectorbt enters one bar earlier and will look slightly
    better on a trending series. Trade COUNT is comparable; per-bar P&L is not.
    """
    entries, exits = insider_entries_exits(close, signals, hold_bars=hold_bars)

    pf = vbt.Portfolio.from_signals(
        close=close, entries=entries, exits=exits, init_cash=_INIT_CASH,
        fees=cost_model.commission_per_trade, slippage=cost_model.slippage,
        freq="1D",
    )
    vbt_equity = pf.value()
    vbt_equity.index = pd.DatetimeIndex(close.index)
    vbt_result = BacktestResult(
        engine="vectorbt", equity_curve=vbt_equity, n_trades=int(pf.trades.count())
    )

    ohlcv = pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close,
         "Volume": 1_000_000.0}
    )
    bt = Backtest(
        ohlcv, _make_signal_strategy(entries, exits), cash=_INIT_CASH,
        commission=cost_model.commission_per_trade, spread=cost_model.slippage,
        finalize_trades=True,
    )
    stats = bt.run()
    bt_equity = stats["_equity_curve"]["Equity"]
    bt_equity.index = pd.DatetimeIndex(ohlcv.index)
    bt_result = BacktestResult(
        engine="backtesting.py", equity_curve=bt_equity,
        n_trades=int(stats["# Trades"]),
    )
    return {"vectorbt": vbt_result, "backtesting.py": bt_result}
