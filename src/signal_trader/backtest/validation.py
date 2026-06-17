"""Leakage and robustness discipline (Spec §5.4).

- shift_test: lag ALL inputs by one bar and re-run; if performance survives
  unchanged the strategy wasn't using future info, if it collapses there was
  leakage. We report both numbers plus a collapse flag.
- oos_split: chronological in-sample / out-of-sample cut; the OOS tail is
  NEVER touched during model selection.
- anchored_walk_forward: expanding train window, fixed-size forward test
  windows (anchored at the start).

Purging/embargo/CPCV are intentionally absent: no ML, no overlapping labels
in Phase 1 (Spec §16).
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd


def oos_split(
    series: pd.Series, oos_fraction: float = 0.25
) -> tuple[pd.Series, pd.Series]:
    """Chronological in-sample / out-of-sample split."""
    if not 0.0 < oos_fraction < 1.0:
        raise ValueError("oos_fraction must be in (0, 1)")
    cut = int(len(series) * (1.0 - oos_fraction))
    return series.iloc[:cut], series.iloc[cut:]


def shift_test(
    series: pd.Series,
    run: Callable[[pd.Series], float],
    lag: int = 1,
    collapse_tolerance: float = 0.5,
) -> dict[str, object]:
    """Run `run` on the series and on the series shifted by `lag` bars.

    `collapsed` is True when the shifted score drops to <= collapse_tolerance
    of the baseline magnitude — the signature of removed lookahead.
    """
    baseline = run(series)
    shifted = run(series.shift(lag).dropna())
    if baseline == 0:
        collapsed = shifted == 0
    else:
        collapsed = abs(shifted) <= collapse_tolerance * abs(baseline)
    return {"baseline": baseline, "shifted": shifted, "collapsed": collapsed}


def anchored_walk_forward(
    series: pd.Series, n_splits: int = 3, test_size: int = 252
) -> list[tuple[pd.Series, pd.Series]]:
    """Expanding train window + fixed forward test windows, anchored at start."""
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
