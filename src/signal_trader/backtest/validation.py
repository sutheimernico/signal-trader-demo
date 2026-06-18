"""Leakage and robustness discipline (Spec §5.4).

- shift_test: lag only the SIGNAL relative to its asset returns and compare
  Sharpe; a genuine edge survives the extra lag, contemporaneous/future
  leakage collapses. We report both numbers plus a collapse flag.
- oos_split: chronological in-sample / out-of-sample cut; the OOS tail is
  NEVER touched during model selection.
- anchored_walk_forward: expanding train window, fixed-size forward test
  windows (anchored at the start).

Purging/embargo/CPCV are intentionally absent: no ML, no overlapping labels
in Phase 1 (Spec §16).
"""
from __future__ import annotations

import pandas as pd
import quantstats as qs

from signal_trader.config import TRADING_DAYS_PER_YEAR


def oos_split(
    series: pd.Series, oos_fraction: float = 0.25
) -> tuple[pd.Series, pd.Series]:
    """Chronological in-sample / out-of-sample split."""
    if not 0.0 < oos_fraction < 1.0:
        raise ValueError("oos_fraction must be in (0, 1)")
    if not series.index.is_monotonic_increasing:
        raise ValueError(
            "series index must be sorted ascending; an unsorted index would "
            "silently place OOS dates before in-sample"
        )
    cut = int(len(series) * (1.0 - oos_fraction))
    return series.iloc[:cut], series.iloc[cut:]


def shift_test(
    signal: pd.Series,
    returns: pd.Series,
    lag: int = 1,
    collapse_threshold: float = 0.5,
) -> dict[str, object]:
    """Detect lookahead by lagging the SIGNAL relative to its asset returns.

    ``signal[t]`` is the position intended for the period whose asset return is
    ``returns[t]``. A non-leaky signal must be computable from information
    strictly before ``t``, so lagging it one extra bar should not destroy a
    genuine edge. A signal built from contemporaneous/future information loses
    its apparent edge once lagged.

    Lagging only the signal (not the whole price series) avoids the pure
    time-translation that made same-bar lookahead invisible: a leaky
    ``signal = sign(returns)`` yields ``baseline == abs(returns)`` (huge Sharpe)
    but a near-zero shifted Sharpe.

    baseline = Sharpe of ``(signal * returns)``;
    shifted  = Sharpe of ``(signal.shift(lag) * returns)``;
    ``collapsed`` is True when ``abs(shifted) <= collapse_threshold *
    abs(baseline)``.
    """
    baseline_series = (signal * returns).dropna()
    shifted_series = (signal.shift(lag) * returns).dropna()
    baseline = float(
        qs.stats.sharpe(baseline_series, rf=0.0, periods=TRADING_DAYS_PER_YEAR)
    )
    shifted = float(
        qs.stats.sharpe(shifted_series, rf=0.0, periods=TRADING_DAYS_PER_YEAR)
    )
    if baseline == 0:
        collapsed = shifted == 0
    else:
        collapsed = abs(shifted) <= collapse_threshold * abs(baseline)
    return {"baseline": baseline, "shifted": shifted, "collapsed": collapsed}


def anchored_walk_forward(
    series: pd.Series, n_splits: int = 3, test_size: int = 252
) -> list[tuple[pd.Series, pd.Series]]:
    """Expanding train window + fixed forward test windows, anchored at start.

    This only carves the chronological (train, test) index slices. The CALLER
    must run the strategy on each fold slice INDEPENDENTLY — fit/compute signals
    on the train slice, then generate positions on the test slice using only
    that fold's information. Never compute signals on the full series and then
    slice the result: rolling windows, fits, or normalizations spanning the
    full series leak future information backward across fold boundaries.
    """
    windows: list[tuple[pd.Series, pd.Series]] = []
    total = len(series)
    first_train = total - n_splits * test_size
    if first_train <= 0:
        raise ValueError("series too short for requested splits/test_size")
    for i in range(n_splits):
        train_end = first_train + i * test_size
        test_end = train_end + test_size
        windows.append((series.iloc[:train_end], series.iloc[train_end:test_end]))
    return windows


def purged_walk_forward(
    dates: pd.Index,
    n_splits: int = 3,
    test_size: int = 252,
    horizon: int = 5,
    embargo: int = 0,
) -> list[tuple[pd.Index, pd.Index]]:
    """Date-level walk-forward with PURGE + EMBARGO for forward-looking labels.

    For ML datasets where the label at date t spans t+1 .. t+1+horizon, training
    dates within `horizon` of the test window have labels that bleed into the
    test period — they are PURGED. An additional `embargo` of dates is dropped
    so serial correlation just before the test cannot leak either. Returns
    (train_dates, test_dates) per fold; the caller maps dates back to rows.
    Train is anchored/expanding; test windows are fixed-size and contiguous.
    """
    if embargo < 1:
        raise ValueError(
            "embargo must be >= 1: with embargo=0 the last training label's exit "
            "bar lands on the first test bar (one-bar label overlap / leak)"
        )
    dates = pd.Index(dates)
    total = len(dates)
    first_train = total - n_splits * test_size
    if first_train <= 0:
        raise ValueError("index too short for requested splits/test_size")
    folds: list[tuple[pd.Index, pd.Index]] = []
    for i in range(n_splits):
        train_end = first_train + i * test_size
        test_end = train_end + test_size
        purge = horizon + embargo
        train = dates[: max(0, train_end - purge)]
        test = dates[train_end:test_end]
        folds.append((train, test))
    return folds
