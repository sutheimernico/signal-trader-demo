import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.metrics import (
    MetricsReport,
    _psr_variance_term,
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


def test_psr_variance_term_floors_negative_argument():
    # Fat right tail: skew=5, sr=0.5 with moderate kurtosis drives the raw
    # variance term 1 - skew*sr + ((kurt-1)/4)*sr**2 negative, which made the
    # sqrt in PSR raise "math domain error". The guard floors it positive so
    # PSR degrades gracefully instead of crashing.
    raw = 1.0 - 5.0 * 0.5 + ((3.0 - 1.0) / 4.0) * 0.5**2
    assert raw < 0.0  # the pre-guard argument really is negative

    assert _psr_variance_term(sr=0.5, skew=5.0, kurt=3.0) > 0.0


def test_psr_handles_fat_right_tail_in_unit_interval():
    # End-to-end: a strongly right-skewed return series still yields a PSR in
    # [0, 1] (never raises) now that the variance term is guarded.
    rng = np.random.default_rng(42)
    base = rng.normal(0.0, 0.001, 2000)
    jumps = rng.random(2000) < 0.01
    r = pd.Series(base + jumps * rng.uniform(0.05, 0.15, 2000))
    assert r.skew() > 3.0  # fat right tail as designed

    psr = probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0)

    assert 0.0 <= psr <= 1.0


def test_cagr_uses_trading_years_not_calendar_days():
    # 252 daily returns compounding to exactly +10% over one trading year.
    # The old quantstats path divided calendar days (~351) by 252, inflating
    # the year count to ~1.39 and understating CAGR to ~7%.
    n = 252
    daily = 1.10 ** (1 / n) - 1
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    r = pd.Series([daily] * n, index=idx)

    rep = compute_metrics(r)

    assert rep.cagr == pytest.approx(0.10, abs=0.005)
