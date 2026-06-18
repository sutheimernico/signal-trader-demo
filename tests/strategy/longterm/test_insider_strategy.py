import datetime as dt

import pandas as pd

from signal_trader.store.signal_store import StoredSignal
from signal_trader.strategy.longterm.insider_strategy import insider_entries_exits


def _sig(known):
    return StoredSignal(
        ticker="AAPL", source="insider_form4", signal_type="insider_cluster_purchase",
        direction="long", timestamp_event=dt.date(2024, 1, 1),
        timestamp_known=known, price_at_known=100.0, raw_payload_json="{}",
        confidence=0.6,
    )


def _close():
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    return pd.Series([100.0 + i for i in range(30)], index=idx)


def test_entry_fires_on_bar_strictly_after_known():
    close = _close()
    known = close.index[3].date()
    entries, exits = insider_entries_exits(close, [_sig(known)], hold_bars=5)
    assert not entries.iloc[:4].any()           # nothing on/before known bar
    assert bool(entries.iloc[4])                # first bar AFTER known
    assert len(entries) == len(close)


def test_exit_fires_hold_bars_after_entry():
    close = _close()
    known = close.index[3].date()
    entries, exits = insider_entries_exits(close, [_sig(known)], hold_bars=5)
    assert bool(exits.iloc[4 + 5])


def test_no_entries_without_signals():
    close = _close()
    entries, exits = insider_entries_exits(close, [], hold_bars=5)
    assert not entries.any() and not exits.any()


def test_signal_known_after_data_window_produces_no_entry():
    close = _close()
    entries, exits = insider_entries_exits(close, [_sig(dt.date(2025, 1, 1))], hold_bars=5)
    assert not entries.any()
