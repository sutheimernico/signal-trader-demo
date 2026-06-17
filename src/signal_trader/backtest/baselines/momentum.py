"""Pure momentum baseline signal — harness validation only, not an edge.

Rule: long while close > SMA(lookback), flat otherwise. The signal is
computed from each bar's close, then SHIFTED one bar so a position taken
on the signal trades on the NEXT bar — this is the leakage guard the
shift-test later stresses (signal t -> position t+1 -> return t+2).
"""
from __future__ import annotations

import pandas as pd


def momentum_signals(
    close: pd.Series, lookback: int = 50
) -> tuple[pd.Series, pd.Series]:
    """Return (entries, exits) boolean Series aligned to `close`.

    entries: True while close > SMA(lookback), shifted one bar to avoid
    same-bar lookahead. exits: True while close <= SMA(lookback), shifted
    one bar. Both are state signals (not crossovers), so they remain True
    for each bar the condition holds.
    """
    if lookback <= 0:
        raise ValueError("lookback must be positive")
    sma = close.rolling(lookback).mean()
    above = close > sma
    entries = above.shift(1, fill_value=False).fillna(False).astype(bool)
    exits = (~above).shift(1, fill_value=False).fillna(False).astype(bool)
    entries.index = close.index
    exits.index = close.index
    return entries, exits
