import numpy as np
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.report import FoundationReport, build_foundation_report


def _close(n=400, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.Series(100 * np.exp(rng.normal(0.0006, 0.01, n).cumsum()), index=idx)


def test_report_contains_both_engines_and_benchmark():
    rep = build_foundation_report(_close(), CostModel(0.001, 0.0005), lookback=50)
    assert isinstance(rep, FoundationReport)
    assert set(rep.engine_metrics) == {"backtesting.py", "vectorbt"}
    assert rep.benchmark_metrics is not None


def test_report_quantifies_vectorized_vs_event_driven_gap():
    rep = build_foundation_report(_close(), CostModel(0.001, 0.0005), lookback=50)
    # the headline artifact: a numeric Sharpe difference between engines
    assert isinstance(rep.vectorized_minus_event_driven_sharpe, float)


def test_render_text_mentions_after_cost_benchmark_and_both_engines():
    rep = build_foundation_report(_close(), CostModel(0.001, 0.0005), lookback=50)
    text = rep.render()
    assert "vectorbt" in text and "backtesting.py" in text
    assert "Buy & Hold (after costs)" in text
    assert "PSR" in text
