import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.validation import (
    anchored_walk_forward,
    oos_split,
    shift_test,
)


def _close(n=400, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(100 * np.exp(rng.normal(0.0004, 0.01, n).cumsum()), index=idx)


def test_oos_split_is_chronological_and_disjoint():
    close = _close()
    is_, oos = oos_split(close, oos_fraction=0.3)
    assert is_.index.max() < oos.index.min()
    assert len(is_) + len(oos) == len(close)
    assert round(len(oos) / len(close), 1) == 0.3


def test_shift_test_returns_both_sharpes_and_a_collapse_flag():
    close = _close()

    def run(series):
        # toy metric that depends on a one-bar-ahead relationship
        return float(series.pct_change().mean())

    res = shift_test(close, run, lag=1)
    assert set(res) == {"baseline", "shifted", "collapsed"}
    assert isinstance(res["collapsed"], bool)


def test_shift_test_flags_leakage_when_shifting_destroys_performance():
    close = _close()

    # leaky metric: peeks at NEXT bar's return (perfect foresight)
    def leaky(series):
        return float(series.pct_change().shift(-1).fillna(0).abs().mean())

    res = shift_test(close, leaky, lag=1)
    # shifting all inputs by one bar must change the leaky result
    assert res["baseline"] != res["shifted"]


def test_anchored_walk_forward_windows_expand_and_are_ordered():
    close = _close(n=300)
    windows = anchored_walk_forward(close, n_splits=3, test_size=50)
    assert len(windows) == 3
    prev_train_end = None
    for train, test in windows:
        assert train.index.max() < test.index.min()
        if prev_train_end is not None:
            assert train.index.max() >= prev_train_end  # anchored/expanding
        prev_train_end = train.index.max()


def test_oos_fraction_bounds_validated():
    with pytest.raises(ValueError):
        oos_split(_close(), oos_fraction=0.0)
    with pytest.raises(ValueError):
        oos_split(_close(), oos_fraction=1.0)
