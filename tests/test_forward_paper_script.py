import datetime as dt
import sys
from unittest.mock import patch

import scripts.run_forward_paper as fwd

from signal_trader.paper.broker import Fill
from signal_trader.store.signal_store import SignalRecord, SignalStore
from signal_trader.store.suggestion_store import SuggestionStore


class FakeBroker:
    def __init__(self, *a, **k):
        pass

    def submit_market_buy(self, symbol, qty):
        return Fill(order_id="b", symbol=symbol, qty=qty, price=151.0,
                    filled_at=dt.datetime(2024, 1, 16, 15, 0, tzinfo=dt.UTC),
                    side="buy")

    def submit_market_sell(self, symbol, qty):
        return Fill(order_id="s", symbol=symbol, qty=qty, price=160.0,
                    filled_at=dt.datetime(2024, 6, 1, 15, 0, tzinfo=dt.UTC),
                    side="sell")


def _signal(store, ticker, known, acc):
    store.insert_signals([SignalRecord(
        ticker=ticker, source="insider_form4",
        signal_type="insider_cluster_purchase", direction="long",
        timestamp_event=dt.date(2024, 1, 1), timestamp_known=known,
        price_at_known=150.0, raw_payload={"accession_no": acc}, confidence=0.6,
    )])


def test_forward_paper_end_to_end(tmp_path, monkeypatch, capsys):
    db = tmp_path / "t.sqlite"
    _signal(SignalStore(db), "AAPL", dt.date(2024, 1, 12), "a")

    monkeypatch.setattr(fwd.config, "SQLITE_PATH", db)
    monkeypatch.setattr(fwd, "AlpacaPaperBroker", FakeBroker)
    monkeypatch.setattr(fwd.config, "alpaca_credentials", lambda: ("k", "s"))

    # build suggestions, then a user accepts one (mimicking the dashboard)
    with patch.object(sys, "argv", ["run_forward_paper.py", "--build-only"]):
        fwd.main()
    SuggestionStore(db).record_decision(
        ticker="AAPL", created_at=dt.date(2024, 1, 12),
        decision="accepted", decided_at=dt.date(2024, 1, 15),
    )

    with patch.object(sys, "argv",
                      ["run_forward_paper.py", "--hold-days", "5"]):
        fwd.main()
    out = capsys.readouterr().out
    assert "Forward paper" in out
    assert "plumbing validation" in out.lower()
    assert "opened" in out.lower()
