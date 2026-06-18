"""Forward return of a signal, anchored point-in-time at timestamp_known.

Entry is the FIRST bar STRICTLY AFTER timestamp_known (an outsider learns of
the filing on the known date and can only trade the next session), and the
exit is `horizon` bars later. Returns None when the cache lacks enough forward
bars — we never truncate the horizon silently to manufacture a number.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd


def forward_return(
    close: pd.Series, timestamp_known: dt.date, horizon: int = 5
) -> float | None:
    """Return over `horizon` bars from the bar after `timestamp_known`."""
    after = close.loc[close.index > pd.Timestamp(timestamp_known)]
    if len(after) < horizon + 1:
        return None
    entry = float(after.iloc[0])
    exit_ = float(after.iloc[horizon])
    if entry == 0:
        return None
    return exit_ / entry - 1.0
