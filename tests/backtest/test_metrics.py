import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.metrics import (
    MetricsReport,
    compute_metrics,
    probabilistic_sharpe_ratio,
)


def _returns(mean=0.0008, vol=0.01, n=756, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(rng.normal(mean, vol, n), index=idx)


def test_compute_metrics_returns_report_with_all_fields():
    rep = compute_metrics(_returns())
    assert isinstance(rep, MetricsReport)
    for field in ("cagr", "sharpe", "sortino", "calmar", "max_drawdown", "psr"):
        assert isinstance(getattr(rep, field), float)


def test_psr_in_unit_interval():
    psr = probabilistic_sharpe_ratio(_returns(), benchmark_sharpe=0.0)
    assert 0.0 <= psr <= 1.0


def test_psr_rises_with_more_evidence_of_positive_sharpe():
    strong = _returns(mean=0.0015, vol=0.008, n=1500, seed=2)
    weak = _returns(mean=0.0002, vol=0.02, n=120, seed=3)
    assert (
        probabilistic_sharpe_ratio(strong, 0.0)
        > probabilistic_sharpe_ratio(weak, 0.0)
    )


def test_psr_against_higher_benchmark_is_lower():
    r = _returns()
    assert (
        probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0)
        >= probabilistic_sharpe_ratio(r, benchmark_sharpe=1.0)
    )


def test_psr_rejects_too_few_observations():
    with pytest.raises(ValueError):
        probabilistic_sharpe_ratio(pd.Series([0.01]), 0.0)
