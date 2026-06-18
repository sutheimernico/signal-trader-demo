import datetime as dt

from signal_trader.signals.consolidate.suggestion_builder import build_suggestions
from signal_trader.store.signal_store import SignalRecord, SignalStore
from signal_trader.store.suggestion_store import SuggestionStore


def _sig(ticker, known, conf, acc):
    return SignalRecord(
        ticker=ticker, source="insider_form4",
        signal_type="insider_cluster_purchase", direction="long",
        timestamp_event=dt.date(2024, 1, 1), timestamp_known=known,
        price_at_known=100.0, raw_payload={"accession_no": acc}, confidence=conf,
    )


def test_builds_one_suggestion_per_ticker_with_pit_created_at(tmp_path):
    sig_store = SignalStore(tmp_path / "t.sqlite")
    sug_store = SuggestionStore(tmp_path / "t.sqlite")
    sig_store.insert_signals([
        _sig("AAPL", dt.date(2024, 1, 2), 0.4, "a"),
        _sig("AAPL", dt.date(2024, 1, 5), 0.6, "b"),
        _sig("MSFT", dt.date(2024, 1, 3), 0.5, "c"),
    ])
    n = build_suggestions(
        sig_store, sug_store, source="insider_form4", horizon="long"
    )
    assert n == 2
    rows = {r.ticker: r for r in sug_store.read_suggestions()}
    assert rows["AAPL"].consolidated_score == 1.0
    # created_at is the LATEST contributing known date (PIT)
    assert rows["AAPL"].created_at == dt.date(2024, 1, 5)
    assert rows["AAPL"].latest_known == dt.date(2024, 1, 5)
    assert rows["AAPL"].status == "open"
    assert rows["AAPL"].horizon == "long"


def test_idempotent_rerun_does_not_duplicate(tmp_path):
    sig_store = SignalStore(tmp_path / "t.sqlite")
    sug_store = SuggestionStore(tmp_path / "t.sqlite")
    sig_store.insert_signals([_sig("AAPL", dt.date(2024, 1, 2), 0.4, "a")])
    build_suggestions(sig_store, sug_store, source="insider_form4")
    build_suggestions(sig_store, sug_store, source="insider_form4")
    assert len(sug_store.read_suggestions()) == 1


def test_no_signals_yields_no_suggestions(tmp_path):
    sig_store = SignalStore(tmp_path / "t.sqlite")
    sug_store = SuggestionStore(tmp_path / "t.sqlite")
    assert build_suggestions(sig_store, sug_store, source="insider_form4") == 0
    assert sug_store.read_suggestions() == []


def test_suggestion_surfaces_source_links(tmp_path):
    import json as _json
    sig_store = SignalStore(tmp_path / "t.sqlite")
    sug_store = SuggestionStore(tmp_path / "t.sqlite")
    sig_store.insert_signals([SignalRecord(
        ticker="KEY", source="insider_form4",
        signal_type="insider_cluster_purchase", direction="long",
        timestamp_event=dt.date(2023, 5, 1), timestamp_known=dt.date(2023, 5, 4),
        price_at_known=10.0,
        raw_payload={"accession_no": "a", "sources": ["https://sec.gov/x", "https://sec.gov/y"]},
        confidence=0.6,
    )])
    build_suggestions(sig_store, sug_store, source="insider_form4")
    s = sug_store.read_suggestions()[0]
    cs = _json.loads(s.contributing_signals_json)
    assert cs["sources"] == ["https://sec.gov/x", "https://sec.gov/y"]
