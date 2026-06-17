import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.benchmark import buy_and_hold_equity
from signal_trader.backtest.costs import CostModel


def test_buy_and_hold_tracks_price_minus_entry_costs():
    close = pd.Series(
        [100.0, 110.0, 120.0],
        index=pd.date_range("2020-01-01", periods=3, freq="B"),
    )
    eq = buy_and_hold_equity(close, CostModel(0.0, 0.0), init_cash=1000.0)
    # no costs: 10 shares * price
    assert eq.iloc[0] == 1000.0
    assert eq.iloc[-1] == 1200.0


def test_costs_reduce_benchmark_equity():
    close = pd.Series(
        np.linspace(100, 150, 50),
        index=pd.date_range("2020-01-01", periods=50, freq="B"),
    )
    free = buy_and_hold_equity(close, CostModel(0.0, 0.0))
    costly = buy_and_hold_equity(close, CostModel(0.005, 0.002))
    assert costly.iloc[-1] < free.iloc[-1]


def test_equity_aligned_to_price_index():
    close = pd.Series(
        np.linspace(100, 150, 50),
        index=pd.date_range("2020-01-01", periods=50, freq="B"),
    )
    eq = buy_and_hold_equity(close, CostModel(0.001, 0.0))
    assert eq.index.equals(close.index)


def test_commission_charged_on_invested_notional():
    # Engines charge commission on the traded notional, not on gross cash.
    # So shares satisfy: shares * entry_price * (1 + commission) == init_cash.
    close = pd.Series(
        [100.0, 100.0],
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    commission = 0.01
    init_cash = 1000.0
    eq = buy_and_hold_equity(
        close, CostModel(commission, 0.0), init_cash=init_cash
    )
    expected_shares = init_cash / (100.0 * (1 + commission))
    assert eq.iloc[0] == pytest.approx(expected_shares * 100.0)
