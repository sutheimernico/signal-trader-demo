import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.engine.vectorbt_engine import VectorbtAdapter
from signal_trader.backtest.result import BacktestResult


def test_run_returns_backtest_result(trending_close):
    result = VectorbtAdapter(
        CostModel(commission_per_trade=0.001, slippage=0.0005)
    ).run(trending_close, lookback=20)
    assert isinstance(result, BacktestResult)
    assert result.engine == "vectorbt"
    assert isinstance(result.equity_curve, pd.Series)
    assert len(result.equity_curve) == len(trending_close)


def test_costs_reduce_final_equity(trending_close):
    free = VectorbtAdapter(
        CostModel(commission_per_trade=0.0, slippage=0.0)
    ).run(trending_close, lookback=20)
    costly = VectorbtAdapter(
        CostModel(commission_per_trade=0.02, slippage=0.01)
    ).run(trending_close, lookback=20)
    if free.n_trades > 0:
        assert costly.equity_curve.iloc[-1] <= free.equity_curve.iloc[-1]


def test_equity_curve_indexed_by_date(trending_close):
    result = VectorbtAdapter(
        CostModel(commission_per_trade=0.001, slippage=0.0)
    ).run(trending_close, lookback=20)
    assert isinstance(result.equity_curve.index, pd.DatetimeIndex)
