import datetime as dt

import pandas as pd

from signal_trader.signals.scoring.forward_return import forward_return


def _close():
    idx = pd.date_range("2024-01-01", periods=40, freq="B")
    return pd.Series([100.0 + i for i in range(40)], index=idx)


def test_forward_return_is_entry_to_horizon_close():
    close = _close()
    known = dt.date(2024, 1, 1)
    # entry on FIRST bar strictly after known; return over `horizon` bars
    fr = forward_return(close, known, horizon=5)
    bars = close.loc[pd.Timestamp(known):]
    entry = bars.iloc[1]          # bar after known (PIT)
    exit_ = bars.iloc[1 + 5]
    assert abs(fr - (exit_ / entry - 1.0)) < 1e-9


def test_returns_none_when_not_enough_forward_bars():
    close = _close()
    known = close.index[-2].date()
    assert forward_return(close, known, horizon=10) is None


def test_entry_is_strictly_after_known_no_same_bar_fill():
    close = _close()
    known = close.index[0].date()
    fr = forward_return(close, known, horizon=1)
    entry = close.iloc[1]
    exit_ = close.iloc[2]
    assert abs(fr - (exit_ / entry - 1.0)) < 1e-9
