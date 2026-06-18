"""Insider long-term strategy: consolidated signals -> PIT entries/exits.

Both Phase-1 engines consume boolean entries/exits aligned to the close index.
Point-in-time: an entry fires on the FIRST bar STRICTLY AFTER timestamp_known
(the filing is public only from the known date; the earliest tradable bar is
the next session). Exit fires `hold_bars` bars after entry — a fixed holding
period, the simplest rule that exercises the harness. No same-bar fills, so the
Phase-1 shift-test stays meaningful.
"""
from __future__ import annotations

import pandas as pd

from signal_trader.store.signal_store import StoredSignal


def insider_entries_exits(
    close: pd.Series,
    signals: list[StoredSignal],
    hold_bars: int = 5,
) -> tuple[pd.Series, pd.Series]:
    """Boolean (entries, exits) aligned to `close` for the given signals."""
    entries = pd.Series(False, index=close.index)
    exits = pd.Series(False, index=close.index)
    for sig in signals:
        after = close.index[close.index > pd.Timestamp(sig.timestamp_known)]
        if len(after) == 0:
            continue
        entry_ts = after[0]
        entry_pos = close.index.get_loc(entry_ts)
        entries.iloc[entry_pos] = True
        exit_pos = entry_pos + hold_bars
        if exit_pos < len(close):
            exits.iloc[exit_pos] = True
    return entries, exits
