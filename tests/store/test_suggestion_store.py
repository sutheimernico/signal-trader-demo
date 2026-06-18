import datetime as dt

from signal_trader.store.suggestion_store import (
    StoredSuggestion,
    SuggestionRecord,
    SuggestionStore,
)


def _rec(**over):
    base = dict(
        ticker="AAPL",
        consolidated_score=1.2,
        contributing_signals={"sources": ["insider_form4"], "n": 3},
        created_at=dt.date(2024, 1, 12),
        latest_known=dt.date(2024, 1, 12),
        horizon="long",
        status="open",
    )
    base.update(over)
    return SuggestionRecord(**base)


def test_insert_then_read_roundtrip(tmp_path):
    store = SuggestionStore(tmp_path / "t.sqlite")
    store.insert_suggestions([_rec()])
    rows = store.read_suggestions()
    assert len(rows) == 1
    r = rows[0]
    assert isinstance(r, StoredSuggestion)
    assert r.ticker == "AAPL"
    assert r.status == "open"
    assert r.user_decision is None
    assert r.decided_at is None
    assert r.latest_known == dt.date(2024, 1, 12)


def test_dedup_on_ticker_created_at(tmp_path):
    store = SuggestionStore(tmp_path / "t.sqlite")
    store.insert_suggestions([_rec(), _rec()])  # same (ticker, created_at) -> one row
    assert len(store.read_suggestions()) == 1


def test_record_decision_updates_status_and_decided_at(tmp_path):
    store = SuggestionStore(tmp_path / "t.sqlite")
    store.insert_suggestions([_rec()])
    store.record_decision(
        ticker="AAPL", created_at=dt.date(2024, 1, 12),
        decision="accepted", decided_at=dt.date(2024, 1, 15),
    )
    r = store.read_suggestions()[0]
    assert r.status == "accepted"
    assert r.user_decision == "accepted"
    assert r.decided_at == dt.date(2024, 1, 15)


def test_read_filters_by_status(tmp_path):
    store = SuggestionStore(tmp_path / "t.sqlite")
    store.insert_suggestions([
        _rec(ticker="AAPL"),
        _rec(ticker="MSFT"),
    ])
    store.record_decision(
        ticker="MSFT", created_at=dt.date(2024, 1, 12),
        decision="rejected", decided_at=dt.date(2024, 1, 13),
    )
    open_rows = store.read_suggestions(status="open")
    assert [r.ticker for r in open_rows] == ["AAPL"]


def test_record_decision_on_unknown_key_raises(tmp_path):
    import pytest
    store = SuggestionStore(tmp_path / "t.sqlite")
    with pytest.raises(ValueError):
        store.record_decision(ticker="NOPE", created_at=dt.date(2024, 1, 1),
                              decision="accepted", decided_at=dt.date(2024, 1, 2))
