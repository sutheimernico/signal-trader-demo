import datetime as dt

import numpy as np
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.strategy.shortterm.consensus import ConsensusSignal
from signal_trader.strategy.shortterm.evaluate import evaluate_ml
from signal_trader.strategy.shortterm.survivorship import DelistingEvent

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


def test_consensus_signals_flow_into_the_feature_matrix_when_opted_in():
    """A/B opt-in path: when consensus_signals are passed, the forecaster sees the
    consensus column; without them it does not. Same folds/costs either way."""
    universe = _universe()
    seen_cols: list[set] = []

    class ColSpy:
        def fit(self, X, y):
            seen_cols.append(set(X.columns))
        def predict(self, X):
            return np.zeros(len(X))

    # signals known on a date inside the dataset range, for tickers that exist
    signals = [
        ConsensusSignal(ticker="T0", timestamp_known=dt.date(2023, 2, 1),
                        source="insider_form4", actor_id="x"),
        ConsensusSignal(ticker="T1", timestamp_known=dt.date(2023, 2, 1),
                        source="congress_house", actor_id="y"),
    ]
    evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=ColSpy,
        consensus_signals=signals, consensus_window_days=365,
    )
    assert seen_cols, "expected at least one fold to fit"
    assert all("consensus_buyers_known_le_t" in cols for cols in seen_cols)


def test_no_consensus_column_without_signals():
    universe = _universe()
    seen_cols: list[set] = []

    class ColSpy:
        def fit(self, X, y):
            seen_cols.append(set(X.columns))
        def predict(self, X):
            return np.zeros(len(X))

    evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=ColSpy,
    )
    assert seen_cols
    assert all("consensus_buyers_known_le_t" not in cols for cols in seen_cols)


def test_scorecard_reports_shift_test_and_diff_psr_fields():
    """The honest scorecard must carry the empirical leak check (shift_test on
    the ML pick series) and the robust margin metric (PSR of ml_net - base_net),
    not just the regime-inflated absolute PSR."""
    universe = _universe()
    from signal_trader.strategy.shortterm.dataset import build_dataset
    _, y_all = build_dataset(universe, horizon=3, feature_windows=[5, 10])
    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=lambda: PerfectForecaster(y_all),
    )
    assert set(res["ml_shift_test"]) == {"baseline", "shifted", "collapsed"}
    assert isinstance(res["ml_shift_test"]["collapsed"], bool)
    assert isinstance(res["diff_psr"], float)
    assert 0.0 <= res["diff_psr"] <= 1.0
    # n_configs_tested is carried for the deflated-Sharpe / multiple-testing note
    assert res["n_configs_tested"] >= 1


def test_shift_test_collapses_for_a_foresight_ranker():
    """A ranker that picks on the TRUE forward label has an edge that is pure
    timing: shifting the realized return one extra bar must collapse it. This is
    the empirical counterpart to the structural max(fit)<min(predict) argument."""
    universe = _universe()
    from signal_trader.strategy.shortterm.dataset import build_dataset
    _, y_all = build_dataset(universe, horizon=3, feature_windows=[5, 10])
    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=lambda: PerfectForecaster(y_all),
    )
    # the foresight edge is large unlagged and must not survive the extra lag
    assert abs(res["ml_shift_test"]["baseline"]) > abs(res["ml_shift_test"]["shifted"])
    assert res["ml_shift_test"]["collapsed"] is True


def test_diff_psr_below_half_when_ml_loses_to_baseline():
    """When ML does not beat the baseline, the honest margin metric — PSR of the
    difference series against 0 — must be < 0.5 (the difference Sharpe is <= 0).
    A zero-prediction ranker reliably loses to momentum after costs."""
    universe = _universe()

    class ZeroForecaster:
        def fit(self, X, y):
            pass
        def predict(self, X):
            return np.zeros(len(X))

    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=ZeroForecaster,
    )
    assert res["beat_baseline"] is False
    assert res["diff_psr"] < 0.5


def test_n_configs_tested_is_propagated():
    universe = _universe()

    class ZeroForecaster:
        def fit(self, X, y):
            pass
        def predict(self, X):
            return np.zeros(len(X))

    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST, forecaster_factory=ZeroForecaster,
        n_configs_tested=3,
    )
    assert res["n_configs_tested"] == 3


def test_survivorship_stress_shades_a_foresight_ranker_picks():
    """Adversarial survivorship stress: a perfect-foresight ranker that would
    otherwise top-pick a (survivor) name is forced to eat the delisting haircut
    once that name's exit was knowable. The stressed net return must drop below
    the unstressed one — proof the haircut bites the picks, point-in-time."""
    universe = _universe()
    from signal_trader.strategy.shortterm.dataset import build_dataset
    _, y_all = build_dataset(universe, horizon=3, feature_windows=[5, 10])
    common = dict(
        horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST,
        forecaster_factory=lambda: PerfectForecaster(y_all),
    )
    base = evaluate_ml(universe, **common)
    # delist every name early in the OOS span so the haircut lands on real picks
    events = [DelistingEvent(ticker=t, delisted_known=dt.date(2023, 2, 1))
              for t in universe]
    stressed = evaluate_ml(
        universe, **common, delisting_events=events, delisting_haircut=-0.60
    )
    assert stressed["delisting_haircut"] == -0.60
    assert stressed["n_delisted_in_universe"] == len(universe)
    assert stressed["ml_mean_net"] < base["ml_mean_net"]


def test_survivorship_stress_is_off_by_default_and_reports_zero_delisted():
    universe = _universe()
    from signal_trader.strategy.shortterm.dataset import build_dataset
    _, y_all = build_dataset(universe, horizon=3, feature_windows=[5, 10])
    res = evaluate_ml(
        universe, horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST,
        forecaster_factory=lambda: PerfectForecaster(y_all),
    )
    assert res["n_delisted_in_universe"] == 0
    assert res["delisting_haircut"] is None


def test_survivorship_event_for_absent_ticker_is_a_noop():
    """A delisting record for a name NOT in the universe changes nothing and is
    not counted — only names that are actually in the (survivor) universe AND on
    the delisting list can be shaded (the documented partial-correction limit)."""
    universe = _universe()
    from signal_trader.strategy.shortterm.dataset import build_dataset
    _, y_all = build_dataset(universe, horizon=3, feature_windows=[5, 10])
    common = dict(
        horizon=3, feature_windows=[5, 10], n_splits=2, test_size=8,
        top_k=2, cost_model=_COST,
        forecaster_factory=lambda: PerfectForecaster(y_all),
    )
    base = evaluate_ml(universe, **common)
    stressed = evaluate_ml(
        universe, **common,
        delisting_events=[DelistingEvent(ticker="NOT_IN_UNIVERSE",
                                         delisted_known=dt.date(2023, 2, 1))],
        delisting_haircut=-1.0,
    )
    assert stressed["n_delisted_in_universe"] == 0
    assert stressed["ml_mean_net"] == base["ml_mean_net"]
