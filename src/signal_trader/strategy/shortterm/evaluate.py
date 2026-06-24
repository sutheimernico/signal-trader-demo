"""Out-of-sample evaluation of the ML experiment (Phase 4).

Honest measurement, not an edge claim. For each PURGED + EMBARGOED walk-forward
fold: fit the forecaster on training rows ONLY, predict the test rows, and on
each test date go long the top-k names by predicted forward return. Every pick's
realized forward return (the point-in-time label) is charged a round-trip cost
(enter + exit). The SAME procedure runs a momentum baseline (top-k by past
return). `beat_baseline` is reported as-is — a model that loses to momentum after
costs is a finding, not something to hide.

Cost note: net = gross - 2*(commission+slippage) per pick (round trip). The
per-rebalance returns are treated as a return series for Sharpe/PSR; both ML and
baseline use the identical metric, so the comparison is fair even though the
rebalance cadence is the label horizon, not daily.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.metrics import probabilistic_sharpe_ratio
from signal_trader.backtest.validation import purged_walk_forward
from signal_trader.strategy.shortterm.consensus import ConsensusSignal
from signal_trader.strategy.shortterm.dataset import build_dataset
from signal_trader.strategy.shortterm.model import Forecaster


def _top_k_mean(labels: pd.Series, scores: np.ndarray, k: int) -> float:
    order = np.argsort(scores)[::-1][:k]
    return float(labels.iloc[order].mean())


def evaluate_ml(
    close_by_ticker: dict[str, pd.Series],
    *,
    horizon: int,
    feature_windows: list[int],
    n_splits: int,
    test_size: int,
    top_k: int,
    cost_model: CostModel,
    forecaster_factory: Callable[[], Forecaster],
    embargo: int = 1,
    consensus_signals: list[ConsensusSignal] | None = None,
    consensus_window_days: int = 30,
) -> dict:
    """Run purged walk-forward OOS evaluation; return an honest scorecard dict.

    The momentum baseline is computed from price momentum alone and never sees
    the consensus column, so the same folds/costs give a fair price-only-vs-+
    consensus A/B: run this twice with and without ``consensus_signals``.
    """
    X, y = build_dataset(
        close_by_ticker,
        horizon=horizon,
        feature_windows=feature_windows,
        consensus_signals=consensus_signals,
        consensus_window_days=consensus_window_days,
    )
    date_level = X.index.get_level_values("date")
    dates = pd.Index(sorted(date_level.unique()))
    folds = purged_walk_forward(
        dates, n_splits=n_splits, test_size=test_size, horizon=horizon, embargo=embargo
    )
    round_trip = 2.0 * (cost_model.commission_per_trade + cost_model.slippage)
    mom_col = f"ret_{max(feature_windows)}"

    ml_gross: list[float] = []
    ml_net: list[float] = []
    base_net: list[float] = []
    for train_dates, test_dates in folds:
        train_mask = date_level.isin(train_dates)
        if not train_mask.any():
            continue
        model = forecaster_factory()
        model.fit(X[train_mask], y[train_mask])
        for d in test_dates:
            rows = X[date_level == d]
            if len(rows) < top_k:
                continue
            labels = y.loc[rows.index]
            preds = np.asarray(model.predict(rows), dtype=float)
            ml = _top_k_mean(labels, preds, top_k)
            base = _top_k_mean(labels, rows[mom_col].to_numpy(), top_k)
            ml_gross.append(ml)
            ml_net.append(ml - round_trip)
            base_net.append(base - round_trip)

    n = len(ml_net)
    ml_series = pd.Series(ml_net, dtype=float)
    base_series = pd.Series(base_net, dtype=float)
    ml_mean = float(ml_series.mean()) if n else 0.0
    base_mean = float(base_series.mean()) if n else 0.0
    return {
        "n_rebalances": n,
        "ml_mean_gross": float(np.mean(ml_gross)) if ml_gross else 0.0,
        "ml_mean_net": ml_mean,
        "baseline_mean_net": base_mean,
        "ml_psr": probabilistic_sharpe_ratio(ml_series) if n > 2 else 0.0,
        "baseline_psr": probabilistic_sharpe_ratio(base_series) if n > 2 else 0.0,
        "beat_baseline": bool(ml_mean > base_mean),
    }
