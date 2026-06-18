import datetime as dt
import json
import logging

from signal_trader.store.signal_store import SignalRecord, SignalStore


def _rec(**over):
    base = dict(
        ticker="AAPL", source="insider_form4", signal_type="open_market_purchase",
        direction="long",
        timestamp_event=dt.date(2024, 1, 10),
        timestamp_known=dt.date(2024, 1, 12),
        price_at_known=150.0,
        raw_payload={"accession_no": "a", "shares": 1000.0},
        confidence=0.7,
    )
    base.update(over)
    return SignalRecord(**base)


def test_insert_then_read_roundtrip(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec()])
    rows = store.read_signals(source="insider_form4")
    assert len(rows) == 1
    r = rows[0]
    assert r.ticker == "AAPL"
    assert r.timestamp_known == dt.date(2024, 1, 12)
    assert r.price_at_known == 150.0
    assert json.loads(r.raw_payload_json)["shares"] == 1000.0


def test_dedup_on_source_ticker_known_accession(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec(), _rec()])  # identical -> one row
    assert len(store.read_signals(source="insider_form4")) == 1


def test_read_filters_by_known_date_window(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([
        _rec(timestamp_known=dt.date(2024, 1, 12),
             raw_payload={"accession_no": "a"}),
        _rec(timestamp_known=dt.date(2024, 6, 1),
             raw_payload={"accession_no": "b"}),
    ])
    rows = store.read_signals(source="insider_form4", end="2024-02-01")
    assert len(rows) == 1
    assert rows[0].timestamp_known == dt.date(2024, 1, 12)


def test_price_at_known_may_be_none_when_no_bar(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec(price_at_known=None,
                               raw_payload={"accession_no": "c"})])
    assert store.read_signals(source="insider_form4")[0].price_at_known is None


# Fix 4: surface silently-ignored re-ingests
def test_duplicate_reinsert_emits_info_log(tmp_path, caplog):
    """Re-inserting a record with an existing PK must log how many were left unchanged."""
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec()])  # first insert
    with caplog.at_level(logging.DEBUG, logger="signal_trader.store.signal_store"):
        store.insert_signals([_rec()])  # duplicate -> INSERT OR IGNORE silently ignores
    assert any(
        "existing" in r.message.lower()
        or "unchanged" in r.message.lower()
        or "ignored" in r.message.lower()
        for r in caplog.records
    )


def test_source_score_upsert_and_read(tmp_path):
    from signal_trader.store.signal_store import SignalStore, SourceScoreRecord
    store = SignalStore(tmp_path / "t.sqlite")
    store.upsert_source_score(SourceScoreRecord(
        source="insider_form4", window="5d", n_signals=10,
        hit_rate=0.6, avg_forward_return=0.012, avg_data_lag_days=2.5,
    ))
    store.upsert_source_score(SourceScoreRecord(
        source="insider_form4", window="5d", n_signals=12,
        hit_rate=0.5, avg_forward_return=0.009, avg_data_lag_days=2.7,
    ))  # same (source, window) -> replace
    scores = store.read_source_scores()
    assert len(scores) == 1
    assert scores[0].n_signals == 12
    assert scores[0].avg_data_lag_days == 2.7
