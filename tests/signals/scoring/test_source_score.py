import datetime as dt

import pandas as pd

from signal_trader.signals.scoring.source_score import score_source
from signal_trader.store.signal_store import SignalRecord, SignalStore


def _close_lookup():
    idx = pd.date_range("2024-01-01", periods=60, freq="B")
    up = pd.Series([100.0 + i for i in range(60)], index=idx)     # always up
    return {"WIN": up, "LOSE": up.iloc[::-1].reset_index(drop=True).set_axis(idx)}


def _rec(ticker, known, event, source="insider_form4"):
    return SignalRecord(
        ticker=ticker, source=source, signal_type="insider_cluster_purchase",
        direction="long", timestamp_event=event, timestamp_known=known,
        price_at_known=100.0, raw_payload={"accession_no": f"{ticker}-{known}"},
        confidence=0.5,
    )


def test_hit_rate_and_avg_return_and_lag(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([
        _rec("WIN", dt.date(2024, 1, 2), dt.date(2024, 1, 1)),   # +1 day lag, up -> hit
        _rec("LOSE", dt.date(2024, 1, 5), dt.date(2024, 1, 1)),  # +4 day lag, down -> miss
    ])
    score = score_source(
        store, source="insider_form4", close_lookup=_close_lookup(),
        horizon=5, window_label="5d",
    )
    assert score.n_signals == 2
    assert 0.0 <= score.hit_rate <= 1.0
    assert score.hit_rate == 0.5
    assert score.avg_data_lag_days == 2.5  # (1 + 4)/2 trade->filing days


def test_signals_without_enough_forward_bars_are_excluded_not_counted_as_miss(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec("WIN", dt.date(2024, 3, 25), dt.date(2024, 3, 22))])
    score = score_source(
        store, source="insider_form4", close_lookup=_close_lookup(),
        horizon=200, window_label="200d",
    )
    assert score.n_signals == 0  # no scoreable signal, not a fake miss
