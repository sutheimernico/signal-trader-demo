import datetime as dt

import pandas as pd

from signal_trader.strategy.shortterm.consensus import ConsensusSignal
from signal_trader.strategy.shortterm.dataset import build_dataset


def _close(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="B")
    return pd.Series([float(v) for v in values], index=idx)


def _csig(ticker, known, source="insider_form4", actor="a"):
    return ConsensusSignal(
        ticker=ticker, timestamp_known=dt.date.fromisoformat(known),
        source=source, actor_id=actor,
    )


def test_label_is_forward_return_entry_next_bar_over_horizon():
    close = _close([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110])
    X, y = build_dataset({"AAA": close}, horizon=2, feature_windows=[2, 3])
    # pick a row well inside the valid range
    ticker, date = "AAA", close.index[4]
    pos = close.index.get_loc(date)
    entry = close.iloc[pos + 1]            # next bar (PIT)
    exit_ = close.iloc[pos + 1 + 2]        # +horizon bars later
    assert abs(y.loc[(ticker, date)] - (exit_ / entry - 1.0)) < 1e-9


def test_features_use_only_past_and_present_not_future():
    close = _close([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21])
    X, _ = build_dataset({"AAA": close}, horizon=2, feature_windows=[2, 3])
    ticker, date = "AAA", close.index[5]
    pos = close.index.get_loc(date)
    expected_ret2 = close.iloc[pos] / close.iloc[pos - 2] - 1.0
    assert abs(X.loc[(ticker, date), "ret_2"] - expected_ret2) < 1e-9
    assert {"ret_2", "vol_2", "ret_3", "vol_3"} <= set(X.columns)


def test_rows_without_full_feature_or_label_window_are_dropped_not_filled():
    close = _close([100, 101, 102, 103, 104, 105, 106, 107])
    X, y = build_dataset({"AAA": close}, horizon=2, feature_windows=[3])
    # first 3 rows lack the feature window; last (1+horizon)=3 lack the label
    assert not X.isna().any().any()
    assert not y.isna().any()
    assert len(X) == len(y)
    dates = [d for (_, d) in X.index]
    assert close.index[0] not in dates       # dropped (no feature window)
    assert close.index[-1] not in dates       # dropped (no forward label)


def test_multi_ticker_indexed_by_ticker_and_date():
    a = _close([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
    b = _close([50, 51, 50, 52, 53, 52, 54, 55, 54, 56])
    X, y = build_dataset({"AAA": a, "BBB": b}, horizon=2, feature_windows=[2])
    assert set(t for (t, _) in X.index) == {"AAA", "BBB"}


def test_interior_nan_price_drops_rows_never_fabricates_zero_vol():
    import numpy as np
    vals = [100, 101, np.nan, 103, 104, 105, 106, 107, 108, 109, 110, 111]
    close = _close([v if v == v else float("nan") for v in vals])
    X, y = build_dataset({"AAA": close}, horizon=2, feature_windows=[2])
    # no fabricated rows, no zero-vol smuggled in around the gap
    assert not X.isna().any().any()
    assert (X["vol_2"] > 0).all()


# --- opt-in consensus feature (same _add_calendar opt-in pattern, default OFF) ---

_CLOSE12 = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110]


def test_consensus_feature_off_by_default():
    close = _close(_CLOSE12)
    X, _ = build_dataset({"AAA": close}, horizon=2, feature_windows=[2, 3])
    assert "consensus_buyers_known_le_t" not in X.columns


def test_consensus_feature_added_only_when_signals_passed():
    close = _close(_CLOSE12)
    signals = [_csig("AAA", "2024-01-01", actor="x")]
    X, _ = build_dataset(
        {"AAA": close}, horizon=2, feature_windows=[2, 3],
        consensus_signals=signals, consensus_window_days=365,
    )
    assert "consensus_buyers_known_le_t" in X.columns
    # one buyer known well before every retained bar -> all rows count >= 1
    assert (X["consensus_buyers_known_le_t"] >= 1).all()


def test_consensus_feature_is_point_in_time_no_forward_leak():
    """Dataset-level as-of guard: a signal known the day AFTER a bar must not
    raise that bar's consensus count."""
    close = _close(_CLOSE12)
    # signal known on the 6th business day; bars strictly before it must read 0
    dates = close.index
    known_day = dates[5].date().isoformat()
    X, _ = build_dataset(
        {"AAA": close}, horizon=2, feature_windows=[2, 3],
        consensus_signals=[_csig("AAA", known_day, actor="x")],
        consensus_window_days=365,
    )
    col = X["consensus_buyers_known_le_t"]
    for (_ticker, date), val in col.items():
        if date < dates[5]:
            assert val == 0, f"forward leak: bar {date} saw a signal known at {known_day}"
        else:
            assert val == 1


def test_consensus_missing_signals_zero_without_dropping_or_fabricating_rows():
    close = _close(_CLOSE12)
    base_X, _ = build_dataset({"AAA": close}, horizon=2, feature_windows=[2, 3])
    X, _ = build_dataset(
        {"AAA": close}, horizon=2, feature_windows=[2, 3],
        consensus_signals=[], consensus_window_days=30,
    )
    # exact same rows as the price-only build: no row dropped, none fabricated
    assert list(X.index) == list(base_X.index)
    assert (X["consensus_buyers_known_le_t"] == 0).all()
