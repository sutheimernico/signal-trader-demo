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


def test_shift_test_flags_leaky_signal():
    # leaky: signal is the sign of the SAME-bar return (contemporaneous peek).
    # baseline (sign(r) * r == abs(r)) has a huge Sharpe; lagging the signal
    # one bar destroys the edge -> collapsed.
    rng = np.random.default_rng(11)
    returns = pd.Series(rng.normal(0.0003, 0.012, 500))
    signal = np.sign(returns)

    res = shift_test(signal, returns, lag=1)

    assert res["collapsed"] is True
    assert res["baseline"] > 10.0


def test_shift_test_passes_clean_signal():
    # clean: momentum position computed from PAST prices only. Lagging the
    # already-lagged position one more bar degrades only modestly on a
    # trending series -> not collapsed.
    rng = np.random.default_rng(13)
    close = pd.Series(100 * np.exp(rng.normal(0.0008, 0.01, 500).cumsum()))
    returns = close.pct_change().fillna(0.0)
    position = (close > close.rolling(20).mean()).shift(1).astype(float)

    res = shift_test(position, returns, lag=1)

    assert res["collapsed"] is False


def test_shift_test_returns_both_sharpes_and_a_collapse_flag():
    rng = np.random.default_rng(7)
    returns = pd.Series(rng.normal(0.0004, 0.01, 400))
    signal = pd.Series(1.0, index=returns.index)

    res = shift_test(signal, returns, lag=1)
    assert set(res) == {"baseline", "shifted", "collapsed"}
    assert isinstance(res["collapsed"], bool)


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


def test_oos_split_rejects_unsorted_index():
    # A reversed index would silently produce OOS dates earlier than IS.
    close = _close()[::-1]
    assert not close.index.is_monotonic_increasing
    with pytest.raises(ValueError):
        oos_split(close)
