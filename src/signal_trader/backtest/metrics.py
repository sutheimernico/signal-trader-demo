"""Honest metrics: quantstats headline ratios + a self-contained PSR.

Never Sharpe alone (Acceptance §8.6): CAGR, Sharpe, Sortino, Calmar, Max
Drawdown together. PSR (Bailey & Lopez de Prado) reports the probability
that the observed Sharpe exceeds a benchmark Sharpe, correcting for sample
length, skew, and kurtosis — the divergence between Sharpe and PSR is the
information.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd
import quantstats as qs

from signal_trader.config import TRADING_DAYS_PER_YEAR


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
    numerator = (sr - benchmark_sharpe) * math.sqrt(n - 1)
    denominator = math.sqrt(_psr_variance_term(sr, skew, kurt))
    return _normal_cdf(numerator / denominator)


@dataclass
class MetricsReport:
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    psr: float


def compute_metrics(
    returns: pd.Series, periods: int = TRADING_DAYS_PER_YEAR
) -> MetricsReport:
    """Compute the honest metric set from a periodic return series.

    CAGR is annualized over TRADING years (len(r) / periods), not calendar
    days: qs.stats.cagr divides calendar_days by 252, counting ~252 trading
    bars as ~1.39 years and understating CAGR by a constant ~1.45x. We compute
    CAGR ourselves and derive Calmar from it (qs.stats.calmar inherits the
    same bug).
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
    )
