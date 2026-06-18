import datetime as dt

from fastapi.testclient import TestClient

from signal_trader.api.app import create_app
from signal_trader.store.paper_trade_store import PaperTradeRecord, PaperTradeStore
from signal_trader.store.signal_store import SignalStore, SourceScoreRecord
from signal_trader.store.suggestion_store import SuggestionRecord, SuggestionStore


def _seed(db_path):
    sug = SuggestionStore(db_path)
    sug.insert_suggestions([
        SuggestionRecord(
            ticker="AAPL", consolidated_score=1.0,
            contributing_signals={"source": "insider_form4", "n_contributing": 2},
            created_at=dt.date(2024, 1, 12), latest_known=dt.date(2024, 1, 12),
            horizon="long",
        ),
    ])
    sig = SignalStore(db_path)
    sig.upsert_source_score(SourceScoreRecord(
        source="insider_form4", window="5d", n_signals=3,
        hit_rate=0.66, avg_forward_return=0.012, avg_data_lag_days=2.0,
    ))
    pt = PaperTradeStore(db_path)
    pt.insert_trade(PaperTradeRecord(
        ticker="AAPL", side="buy", qty=10.0, entry_price=150.0,
        entry_time=dt.datetime(2024, 1, 15, 14, 30),
        exit_price=None, exit_time=None, pnl=None,
        source_suggestion_id="AAPL|2024-01-12",
    ))


def _client(tmp_path):
    db = tmp_path / "t.sqlite"
    _seed(db)
    return TestClient(create_app(db))


def test_get_suggestions(tmp_path):
    resp = _client(tmp_path).get("/suggestions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["ticker"] == "AAPL"
    assert body[0]["status"] == "open"
    assert body[0]["consolidated_score"] == 1.0


def test_get_source_scores_shows_data_lag(tmp_path):
    body = _client(tmp_path).get("/source-scores").json()
    assert body[0]["source"] == "insider_form4"
    assert body[0]["avg_data_lag_days"] == 2.0  # data-lag always visible (§8.4)


def test_get_paper_trades_open_filter(tmp_path):
    client = _client(tmp_path)
    assert len(client.get("/paper-trades?open_only=true").json()) == 1


def test_post_decision_updates_status(tmp_path):
    client = _client(tmp_path)
    resp = client.post(
        "/suggestions/AAPL/2024-01-12/decision", json={"decision": "accepted"}
    )
    assert resp.status_code == 200
    after = client.get("/suggestions?status=accepted").json()
    assert [s["ticker"] for s in after] == ["AAPL"]


def test_post_decision_unknown_returns_404(tmp_path):
    client = _client(tmp_path)
    resp = client.post(
        "/suggestions/NOPE/2024-01-12/decision", json={"decision": "accepted"}
    )
    assert resp.status_code == 404


def test_contributing_signals_is_parsed_object_not_string(tmp_path):
    body = _client(tmp_path).get("/suggestions").json()
    assert body[0]["contributing_signals"]["n_contributing"] == 2


def test_malformed_created_at_is_422_not_404(tmp_path):
    resp = _client(tmp_path).post(
        "/suggestions/AAPL/2024-13-99/decision", json={"decision": "accepted"}
    )
    assert resp.status_code == 422


def test_invalid_decision_value_rejected(tmp_path):
    resp = _client(tmp_path).post(
        "/suggestions/AAPL/2024-01-12/decision", json={"decision": "maybe"}
    )
    assert resp.status_code == 422


def test_cors_allows_vite_dev_origin(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/suggestions", headers={"Origin": "http://localhost:5173"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_serves_frontend_index_when_build_present(tmp_path):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html><body>KIT dashboard</body></html>")
    db = tmp_path / "t.sqlite"
    _seed(db)
    from signal_trader.api.app import create_app
    client = TestClient(create_app(db, static_dir=static))
    # API still works
    assert client.get("/source-scores").status_code == 200
    # and the SPA index is served at root
    root = client.get("/")
    assert root.status_code == 200
    assert "KIT dashboard" in root.text
