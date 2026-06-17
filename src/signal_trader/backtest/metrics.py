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
    denominator = math.sqrt(1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr**2)
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
    """Compute the honest metric set from a periodic return series."""
    r = returns.dropna()
    return MetricsReport(
        cagr=float(qs.stats.cagr(r)),
        sharpe=float(qs.stats.sharpe(r, rf=0.0, periods=periods)),
        sortino=float(qs.stats.sortino(r, rf=0.0, periods=periods, annualize=True)),
        calmar=float(qs.stats.calmar(r)),
        max_drawdown=float(qs.stats.max_drawdown((1 + r).cumprod())),
        psr=probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0),
    )
