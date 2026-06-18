import datetime as dt

from signal_trader.paper.broker import Fill
from signal_trader.paper.loop import close_due_trades
from signal_trader.store.paper_trade_store import PaperTradeRecord, PaperTradeStore


class SellBroker:
    def __init__(self, price=160.0):
        self.price = price
        self.sells = []

    def submit_market_sell(self, symbol: str, qty: float) -> Fill:
        self.sells.append((symbol, qty))
        return Fill(order_id=f"sell-{symbol}", symbol=symbol, qty=qty,
                    price=self.price, filled_at=dt.datetime(2024, 1, 25, 15, 0),
                    side="sell")


_UTC = dt.UTC


def _open_trade(store, ticker="AAPL",
                entry=dt.datetime(2024, 1, 16, 15, 0, tzinfo=_UTC),
                entry_price=150.0, sid="AAPL|2024-01-12"):
    store.insert_trade(PaperTradeRecord(
        ticker=ticker, side="buy", qty=10.0, entry_price=entry_price,
        entry_time=entry, exit_price=None, exit_time=None, pnl=None,
        source_suggestion_id=sid,
    ))


def test_closes_trade_after_hold_period_with_real_fill_pnl(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    _open_trade(store)
    broker = SellBroker(price=160.0)
    n = close_due_trades(store, broker, as_of=dt.datetime(2024, 1, 30, tzinfo=_UTC), hold_days=5)
    assert n == 1
    r = store.read_trades()[0]
    assert r.exit_price == 160.0
    assert r.pnl == (160.0 - 150.0) * 10.0  # from the actual sell fill
    assert r.exit_time == dt.datetime(2024, 1, 25, 15, 0)


def test_does_not_close_before_hold_period(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    _open_trade(store, entry=dt.datetime(2024, 1, 16, 15, 0, tzinfo=_UTC))
    broker = SellBroker()
    # only 3 days elapsed, hold is 5
    n = close_due_trades(store, broker, as_of=dt.datetime(2024, 1, 19, tzinfo=_UTC), hold_days=5)
    assert n == 0
    assert broker.sells == []
    assert store.read_trades(open_only=True)


def test_already_closed_trades_are_left_alone(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    _open_trade(store)
    broker = SellBroker()
    close_due_trades(store, broker, as_of=dt.datetime(2024, 1, 30, tzinfo=_UTC), hold_days=5)
    n2 = close_due_trades(store, broker, as_of=dt.datetime(2024, 2, 10, tzinfo=_UTC), hold_days=5)
    assert n2 == 0
    assert len(broker.sells) == 1  # not sold twice
