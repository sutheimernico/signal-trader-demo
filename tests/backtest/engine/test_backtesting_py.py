import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.engine.backtesting_py import BacktestingPyAdapter
from signal_trader.backtest.result import BacktestResult


def test_run_returns_backtest_result(ohlcv_frame):
    adapter = BacktestingPyAdapter(CostModel(commission_per_trade=0.001, slippage=0.0))
    result = adapter.run(ohlcv_frame, lookback=20)
    assert isinstance(result, BacktestResult)
    assert result.engine == "backtesting.py"
    assert isinstance(result.equity_curve, pd.Series)
    assert len(result.equity_curve) > 0
    assert result.n_trades >= 0


def test_costs_reduce_final_equity(ohlcv_frame):
    free = BacktestingPyAdapter(
        CostModel(commission_per_trade=0.0, slippage=0.0)
    ).run(ohlcv_frame, lookback=20)
    costly = BacktestingPyAdapter(
        CostModel(commission_per_trade=0.02, slippage=0.01)
    ).run(ohlcv_frame, lookback=20)
    if free.n_trades > 0:
        assert costly.equity_curve.iloc[-1] <= free.equity_curve.iloc[-1]


def test_equity_curve_indexed_by_date(ohlcv_frame):
    result = BacktestingPyAdapter(
        CostModel(commission_per_trade=0.001, slippage=0.0)
    ).run(ohlcv_frame, lookback=20)
    assert isinstance(result.equity_curve.index, pd.DatetimeIndex)
