import math

import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.metrics import (
    MetricsReport,
    _psr_from_moments,
    _psr_variance_term,
    compute_metrics,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    per_period_sharpe,
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
    assert rep.dsr is None  # no trial history given -> no DSR to report


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


# --- per_period_sharpe -------------------------------------------------


def test_per_period_sharpe_matches_mean_over_std():
    r = pd.Series([0.01, -0.005, 0.02, 0.0, -0.01])
    expected = r.mean() / r.std(ddof=1)
    assert per_period_sharpe(r) == pytest.approx(expected)


def test_per_period_sharpe_zero_for_degenerate_series():
    assert per_period_sharpe(pd.Series([0.01])) == 0.0
    assert per_period_sharpe(pd.Series([0.01, 0.01, 0.01])) == 0.0  # zero std


# --- expected_max_sharpe (Bailey & Lopez de Prado 2014, eq. 10) --------


def test_expected_max_sharpe_zero_with_fewer_than_two_trials():
    assert expected_max_sharpe(n_trials=0, sharpe_variance=0.5) == 0.0
    assert expected_max_sharpe(n_trials=1, sharpe_variance=0.5) == 0.0


def test_expected_max_sharpe_zero_with_no_dispersion():
    assert expected_max_sharpe(n_trials=100, sharpe_variance=0.0) == 0.0


def test_expected_max_sharpe_matches_paper_worked_example():
    # Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio": 100 trials,
    # Var[SR_trials] = 0.5 annualized (daily: 0.5/252). Independently
    # recomputed from the paper's eq. 10 (see marti.ai's worked write-up of
    # the same paper) -> SR0 ~ 0.11272 (daily scale).
    sr0 = expected_max_sharpe(n_trials=100, sharpe_variance=0.5 / 252)
    assert sr0 == pytest.approx(0.11272, abs=1e-4)


def test_expected_max_sharpe_rises_with_more_trials():
    # More independent tries push the "found by chance" bar higher.
    few = expected_max_sharpe(n_trials=10, sharpe_variance=0.01)
    many = expected_max_sharpe(n_trials=1000, sharpe_variance=0.01)
    assert many > few > 0.0


# --- deflated_sharpe_ratio ----------------------------------------------


def test_deflated_sharpe_ratio_equals_plain_psr_with_one_trial():
    r = _returns()
    dsr = deflated_sharpe_ratio(r, trial_sharpes=[per_period_sharpe(r)])
    assert dsr == pytest.approx(probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0))


def test_deflated_sharpe_ratio_never_exceeds_plain_psr():
    # SR0 >= 0 always (Bailey & Lopez de Prado assume zero-mean null trials),
    # so raising the benchmark from 0 to SR0 can only lower the probability.
    r = _returns(mean=0.001, vol=0.01, n=500, seed=7)
    trial_sharpes = [per_period_sharpe(_returns(seed=s)) for s in range(20)]
    dsr = deflated_sharpe_ratio(r, trial_sharpes)
    psr = probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0)
    assert dsr <= psr


def test_deflated_sharpe_ratio_matches_paper_worked_example():
    # Same worked example as above, carried through the full DSR formula:
    # SR=2.5 annualized, Var[SR_trials]=0.5 annualized, 100 trials, 1250-day
    # backtest, skew=-3, kurtosis=10 -> DSR ~ 0.8997 (independently
    # recomputed from Bailey & Lopez de Prado 2014's formula).
    sr0 = expected_max_sharpe(n_trials=100, sharpe_variance=0.5 / 252)
    dsr = _psr_from_moments(
        sr=2.5 / math.sqrt(252), skew=-3.0, kurt=10.0, n=1250, benchmark_sharpe=sr0
    )
    assert dsr == pytest.approx(0.8997, abs=2e-4)


# --- compute_metrics DSR wiring ------------------------------------------


def test_compute_metrics_dsr_set_when_trial_history_given():
    r = _returns()
    trial_sharpes = [per_period_sharpe(_returns(seed=s)) for s in range(5)]
    rep = compute_metrics(r, trial_sharpes=trial_sharpes)
    assert isinstance(rep.dsr, float)
    assert 0.0 <= rep.dsr <= 1.0
