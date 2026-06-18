import numpy as np
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.strategy.shortterm.evaluate import evaluate_ml

_COST = CostModel(commission_per_trade=0.0005, slippage=0.0005)


def _close(seed, n=80):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0004, 0.02, n)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.Series(100 * (1 + rets).cumprod(), index=idx)


def _universe():
    return {f"T{i}": _close(i) for i in range(8)}


class PerfectForecaster:
    """Cheats by returning the true label — used only to prove the harness ranks
    and scores correctly (a real model never sees y at predict time)."""
    def __init__(self, y):
        self._y = y
    def fit(self, X, y):
        pass
    def predict(self, X):
        return self._y.loc[X.index].to_numpy()


def test_evaluate_runs_oos_and_reports_after_cost_vs_baseline():
    universe = _universe()
    from signal_trader.strategy.shortterm.dataset import build_dataset
    _, y_all = build_dataset(universe, horizon=3, feature_windows=[5, 10])
    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=lambda: PerfectForecaster(y_all),
    )
    assert res["n_rebalances"] > 0
    assert "ml_mean_net" in res and "baseline_mean_net" in res
    assert isinstance(res["beat_baseline"], bool)
    # a perfect-foresight ranker must beat the momentum baseline net of costs
    assert res["ml_mean_net"] >= res["baseline_mean_net"]


def test_costs_reduce_net_return_below_gross():
    universe = _universe()
    from signal_trader.strategy.shortterm.dataset import build_dataset
    _, y_all = build_dataset(universe, horizon=3, feature_windows=[5, 10])
    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=lambda: PerfectForecaster(y_all),
    )
    assert res["ml_mean_net"] < res["ml_mean_gross"]  # costs always bite


def test_each_fold_trains_strictly_before_it_predicts():
    """Per-fold leak detector: a fold's max training date must be strictly before
    its first prediction date (purge+embargo gap). Walk-forward DOES let an
    earlier fold's test become a later fold's train — correct — so the check is
    per fold, not global."""
    universe = _universe()
    detectors = []

    class LeakDetector:
        def __init__(self):
            self.fit_dates: list = []
            self.predict_dates: list = []
            detectors.append(self)
        def fit(self, X, y):
            self.fit_dates += [d for (_, d) in X.index]
        def predict(self, X):
            self.predict_dates += [d for (_, d) in X.index]
            return np.zeros(len(X))

    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=LeakDetector,
    )
    assert res["n_rebalances"] > 0
    active = [d for d in detectors if d.predict_dates]
    assert active, "expected at least one fold to predict"
    for d in active:
        assert max(d.fit_dates) < min(d.predict_dates)  # no train-on-test, with gap
