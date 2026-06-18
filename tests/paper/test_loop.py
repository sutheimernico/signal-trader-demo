import datetime as dt

from signal_trader.paper.broker import Fill
from signal_trader.paper.loop import open_accepted_suggestions
from signal_trader.store.paper_trade_store import PaperTradeStore
from signal_trader.store.suggestion_store import SuggestionRecord, SuggestionStore


class FakeBroker:
    """Records buys and returns a deterministic fill (no network)."""

    def __init__(self):
        self.calls = []

    def submit_market_buy(self, symbol: str, qty: float) -> Fill:
        self.calls.append((symbol, qty))
        return Fill(
            order_id=f"ord-{symbol}-{len(self.calls)}",
            symbol=symbol,
            qty=qty,
            price=151.0,
            filled_at=dt.datetime(2024, 1, 16, 15, 0),
            side="buy",
        )


def _accepted(store, ticker, created):
    store.insert_suggestions([SuggestionRecord(
        ticker=ticker, consolidated_score=1.0,
        contributing_signals={"source": "insider_form4", "n_contributing": 2},
        created_at=created, latest_known=created, horizon="long",
    )])
    store.record_decision(ticker=ticker, created_at=created,
                          decision="accepted", decided_at=dt.date(2024, 1, 16))


def test_opens_one_paper_trade_per_accepted_suggestion(tmp_path):
    sug = SuggestionStore(tmp_path / "t.sqlite")
    trades = PaperTradeStore(tmp_path / "t.sqlite")
    _accepted(sug, "AAPL", dt.date(2024, 1, 12))
    broker = FakeBroker()
    n = open_accepted_suggestions(sug, trades, broker, qty=10.0)
    assert n == 1
    rows = trades.read_trades()
    assert len(rows) == 1
    r = rows[0]
    assert r.ticker == "AAPL"
    assert r.entry_price == 151.0  # from the actual fill, not idealized
    assert r.entry_time == dt.datetime(2024, 1, 16, 15, 0)
    assert r.exit_price is None  # opened, not closed
    assert r.source_suggestion_id == "AAPL|2024-01-12"


def test_open_suggestions_are_not_traded(tmp_path):
    sug = SuggestionStore(tmp_path / "t.sqlite")
    trades = PaperTradeStore(tmp_path / "t.sqlite")
    sug.insert_suggestions([SuggestionRecord(
        ticker="AAPL", consolidated_score=1.0,
        contributing_signals={}, created_at=dt.date(2024, 1, 12),
        latest_known=dt.date(2024, 1, 12), horizon="long",
    )])  # left open, no decision
    n = open_accepted_suggestions(sug, trades, FakeBroker())
    assert n == 0
    assert trades.read_trades() == []


def test_idempotent_does_not_double_open(tmp_path):
    sug = SuggestionStore(tmp_path / "t.sqlite")
    trades = PaperTradeStore(tmp_path / "t.sqlite")
    _accepted(sug, "AAPL", dt.date(2024, 1, 12))
    broker = FakeBroker()
    open_accepted_suggestions(sug, trades, broker)
    n2 = open_accepted_suggestions(sug, trades, broker)
    assert n2 == 0
    assert len(trades.read_trades()) == 1
    assert len(broker.calls) == 1  # no second order


def test_rejected_suggestions_are_not_traded(tmp_path):
    sug = SuggestionStore(tmp_path / "t.sqlite")
    trades = PaperTradeStore(tmp_path / "t.sqlite")
    sug.insert_suggestions([SuggestionRecord(
        ticker="MSFT", consolidated_score=1.0, contributing_signals={},
        created_at=dt.date(2024, 1, 12), latest_known=dt.date(2024, 1, 12),
        horizon="long",
    )])
    sug.record_decision(ticker="MSFT", created_at=dt.date(2024, 1, 12),
                        decision="rejected", decided_at=dt.date(2024, 1, 16))
    assert open_accepted_suggestions(sug, trades, FakeBroker()) == 0


class FlakyBroker:
    def submit_market_buy(self, symbol, qty):
        if symbol == "BAD":
            raise RuntimeError("rejected by broker")
        return Fill(order_id="ok", symbol=symbol, qty=qty, price=10.0,
                    filled_at=dt.datetime(2024, 1, 16, 15, 0), side="buy")


def test_broker_failure_skips_one_does_not_abort_rest(tmp_path):
    sug = SuggestionStore(tmp_path / "t.sqlite")
    trades = PaperTradeStore(tmp_path / "t.sqlite")
    _accepted(sug, "BAD", dt.date(2024, 1, 12))
    _accepted(sug, "GOOD", dt.date(2024, 1, 12))
    n = open_accepted_suggestions(sug, trades, FlakyBroker())
    assert n == 1  # GOOD opened despite BAD failing
    assert [t.ticker for t in trades.read_trades()] == ["GOOD"]
