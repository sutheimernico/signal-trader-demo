"""Honest metrics: quantstats headline ratios + self-contained PSR/DSR.

Never Sharpe alone (Acceptance §8.6): CAGR, Sharpe, Sortino, Calmar, Max
Drawdown together. PSR (Bailey & Lopez de Prado 2012) reports the probability
that the observed Sharpe exceeds a benchmark Sharpe, correcting for sample
length, skew, and kurtosis — the divergence between Sharpe and PSR is the
information. DSR (Bailey & Lopez de Prado 2014, "The Deflated Sharpe Ratio")
raises that benchmark from a fixed 0 to the expected maximum Sharpe you would
see by chance among the trials actually tried (`trial_log.py` supplies the
trial history) — the honest correction for "we tried N configs and reported
the best one".
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

import pandas as pd
import quantstats as qs

from signal_trader.config import TRADING_DAYS_PER_YEAR

_STANDARD_NORMAL = NormalDist()
# Bailey & Lopez de Prado (2014) eq. 10; Euler-Mascheroni constant.
_EULER_MASCHERONI = 0.5772156649015328606


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _psr_variance_term(sr: float, skew: float, kurt: float) -> float:
    """Variance of the Sharpe estimator: ``1 - skew*sr + ((kurt-1)/4)*sr**2``.

    For valid sample moments this stays positive (Pearson's bound forces
    ``kurt >= skew**2 + 1``), but extreme/degenerate moments can drive it
    negative and make the sqrt in PSR raise ``math domain error``. We floor it
    at a tiny positive epsilon so PSR degrades gracefully instead of crashing.
    """
    arg = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr**2
    return max(1e-10, arg)


def _psr_from_moments(
    sr: float, skew: float, kurt: float, n: int, benchmark_sharpe: float
) -> float:
    """PSR/DSR core (Bailey & Lopez de Prado): given the sample Sharpe, its
    skew/kurtosis, the sample length, and a benchmark Sharpe to clear, return
    the probability the true Sharpe exceeds that benchmark. PSR and DSR are
    the SAME formula; DSR just plugs in a higher (trial-corrected) benchmark
    instead of 0 — see `expected_max_sharpe`/`deflated_sharpe_ratio` below.
    """
    numerator = (sr - benchmark_sharpe) * math.sqrt(n - 1)
    denominator = math.sqrt(_psr_variance_term(sr, skew, kurt))
    return _normal_cdf(numerator / denominator)


def per_period_sharpe(returns: pd.Series) -> float:
    """Non-annualized Sharpe: per-period mean / per-period std (ddof=1).

    This is the scale PSR/DSR operate on. It is what callers should log as a
    trial's Sharpe (`trial_log.log_trial`) so the Deflated Sharpe Ratio later
    compares like with like — annualizing first would silently change what
    "variance across trials" means. Returns 0.0 for a <2-observation or
    zero-variance series (a degenerate trial contributes no information,
    matching PSR's own zero-std branch below).
    """
    r = returns.dropna().to_numpy()
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0:
        return 0.0
    return float(r.mean() / std)


def probabilistic_sharpe_ratio(
    returns: pd.Series, benchmark_sharpe: float = 0.0
) -> float:
    """Probability that the true (non-annualized) Sharpe exceeds the
    benchmark, with skew/kurtosis correction.

    Sharpe and benchmark_sharpe are per-period (not annualized) here.
    """
    r = returns.dropna().to_numpy()
    n = r.size
    if n < 2:
        raise ValueError("need at least 2 observations for PSR")
    std = r.std(ddof=1)
    if std == 0:
        return 1.0 if r.mean() > benchmark_sharpe else 0.0
    sr = r.mean() / std
    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurtosis()) + 3.0  # pandas gives excess kurtosis
    return _psr_from_moments(sr, skew, kurt, n, benchmark_sharpe)


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """SR0: the expected maximum Sharpe you'd see among ``n_trials``
    independent, equally-skilled-at-zero trials with observed-Sharpe variance
    ``sharpe_variance`` (Bailey & Lopez de Prado 2014, eq. 10) — the benchmark
    the Deflated Sharpe Ratio holds a result to instead of a flat 0.

    More trials, or more dispersion among them, raises the bar: with enough
    random tries, a high Sharpe shows up by chance alone. Returns 0.0 (no
    correction) with fewer than 2 trials or zero dispersion — there is no
    multiple-testing evidence yet, so DSR should collapse back to plain PSR.
    """
    if n_trials < 2 or sharpe_variance <= 0:
        return 0.0
    z_1 = _STANDARD_NORMAL.inv_cdf(1 - 1 / n_trials)
    z_2 = _STANDARD_NORMAL.inv_cdf(1 - 1 / (n_trials * math.e))
    return math.sqrt(sharpe_variance) * (
        (1 - _EULER_MASCHERONI) * z_1 + _EULER_MASCHERONI * z_2
    )


def deflated_sharpe_ratio(
    returns: pd.Series, trial_sharpes: Sequence[float]
) -> float:
    """PSR benchmarked against the expected-max-Sharpe of the trials tried
    (Bailey & Lopez de Prado 2014) instead of 0 — corrects for selection bias
    from trying multiple parameter variants/strategies before reporting the
    best one.

    ``trial_sharpes`` is the per-period Sharpe (see `per_period_sharpe`) of
    every trial run so far in the SAME comparable search (see
    `trial_log.py`), one entry per trial, in any order. With fewer than 2
    trials this is identical to plain PSR(0) — a single trial carries no
    evidence of a multiple-testing bias to correct for.
    """
    n_trials = len(trial_sharpes)
    variance = (
        float(pd.Series(trial_sharpes, dtype=float).var(ddof=1))
        if n_trials >= 2
        else 0.0
    )
    sr0 = expected_max_sharpe(n_trials, variance)
    return probabilistic_sharpe_ratio(returns, benchmark_sharpe=sr0)


@dataclass
class MetricsReport:
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    psr: float
    dsr: float | None = None


def compute_metrics(
    returns: pd.Series,
    periods: int = TRADING_DAYS_PER_YEAR,
    trial_sharpes: Sequence[float] | None = None,
) -> MetricsReport:
    """Compute the honest metric set from a periodic return series.

    CAGR is annualized over TRADING years (len(r) / periods), not calendar
    days: qs.stats.cagr divides calendar_days by 252, counting ~252 trading
    bars as ~1.39 years and understating CAGR by a constant ~1.45x. We compute
    CAGR ourselves and derive Calmar from it (qs.stats.calmar inherits the
    same bug).

    ``trial_sharpes``, when given, is the trial history from `trial_log.py`
    (per-period Sharpes of every trial tried so far, THIS run included) and
    turns on the Deflated Sharpe Ratio (`dsr`); omitted, `dsr` stays `None` —
    there is no honest DSR without a trial history to deflate against.
    """
    r = returns.dropna()
    max_drawdown = float(qs.stats.max_drawdown((1 + r).cumprod()))
    if len(r) > 0:
        cagr = float((1 + r).prod() ** (periods / len(r)) - 1)
    else:
        cagr = 0.0
    calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else float("nan")
    return MetricsReport(
        cagr=cagr,
        sharpe=float(qs.stats.sharpe(r, rf=0.0, periods=periods)),
        sortino=float(qs.stats.sortino(r, rf=0.0, periods=periods, annualize=True)),
        calmar=calmar,
        max_drawdown=max_drawdown,
        psr=probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0),
        dsr=deflated_sharpe_ratio(r, trial_sharpes) if trial_sharpes else None,
    )
