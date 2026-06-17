import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.baselines.momentum import momentum_signals


def test_entries_and_exits_are_aligned_boolean_series():
    close = pd.Series(np.linspace(100, 120, 60),
                      index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries, exits = momentum_signals(close, lookback=20)
    assert entries.dtype == bool and exits.dtype == bool
    assert entries.index.equals(close.index)
    assert exits.index.equals(close.index)


def test_uptrend_enters_and_downtrend_exits():
    up = pd.Series(np.linspace(100, 200, 60),
                   index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries, exits = momentum_signals(up, lookback=20)
    assert entries.iloc[30:].any()
    down = pd.Series(np.linspace(200, 100, 60),
                     index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries_d, exits_d = momentum_signals(down, lookback=20)
    assert exits_d.iloc[30:].any()


def test_no_signal_during_warmup_window():
    close = pd.Series(np.linspace(100, 120, 60),
                      index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries, exits = momentum_signals(close, lookback=20)
    # SMA undefined for the first `lookback` bars -> no entries there
    assert not entries.iloc[:20].any()


def test_signals_are_shifted_one_bar_to_prevent_lookahead():
    # A close-based signal must act on the NEXT bar, never the same close.
    close = pd.Series(
        [100, 100, 100, 100, 105, 105, 105, 105, 105, 105],
        index=pd.date_range("2020-01-01", periods=10, freq="B"),
        dtype=float,
    )
    entries, _ = momentum_signals(close, lookback=3)
    # the SMA-above condition first holds at position 4; the state-based entry
    # signal appears at position 5 (shifted one bar).
    first_entry = entries.idxmax() if entries.any() else None
    assert first_entry is None or entries.index.get_loc(first_entry) >= 5


def test_lookback_must_be_positive():
    close = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        momentum_signals(close, lookback=0)


def test_no_signal_during_warmup_entries_and_exits():
    """Warmup bars must not produce any entries OR exits.

    During the first `lookback` bars the SMA is NaN, so both conditions are
    semantically undefined.  Before the fix, ~above (NaN -> False) was True,
    producing spurious exits in the warmup window.
    """
    lookback = 20
    close = pd.Series(
        np.linspace(100, 120, 60),
        index=pd.date_range("2020-01-01", periods=60, freq="B"),
    )
    entries, exits = momentum_signals(close, lookback=lookback)
    assert not entries.iloc[:lookback].any(), "entries fired during warmup"
    assert not exits.iloc[:lookback].any(), "exits fired during warmup"
