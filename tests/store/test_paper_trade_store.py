import datetime as dt

import pytest

from signal_trader.store.paper_trade_store import (
    PaperTradeRecord,
    PaperTradeStore,
    StoredPaperTrade,
)


def _rec(**over):
    base = dict(
        ticker="AAPL",
        side="buy",
        qty=10.0,
        entry_price=150.0,
        entry_time=dt.datetime(2024, 1, 15, 14, 30),
        exit_price=None,
        exit_time=None,
        pnl=None,
        source_suggestion_id="AAPL|2024-01-12",
    )
    base.update(over)
    return PaperTradeRecord(**base)


def test_insert_open_trade_roundtrip(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    trade_id = store.insert_trade(_rec())
    rows = store.read_trades()
    assert len(rows) == 1
    r = rows[0]
    assert isinstance(r, StoredPaperTrade)
    assert r.id == trade_id
    assert r.ticker == "AAPL"
    assert r.exit_price is None
    assert r.pnl is None


def test_close_trade_records_exit_and_pnl(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    trade_id = store.insert_trade(_rec())
    store.close_trade(
        trade_id, exit_price=160.0,
        exit_time=dt.datetime(2024, 1, 22, 14, 30), pnl=100.0,
    )
    r = store.read_trades()[0]
    assert r.exit_price == 160.0
    assert r.exit_time == dt.datetime(2024, 1, 22, 14, 30)
    assert r.pnl == 100.0


def test_read_open_trades_only(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    open_id = store.insert_trade(_rec(ticker="AAPL"))
    closed_id = store.insert_trade(_rec(ticker="MSFT"))
    store.close_trade(
        closed_id, exit_price=200.0,
        exit_time=dt.datetime(2024, 1, 20, 14, 30), pnl=50.0,
    )
    open_rows = store.read_trades(open_only=True)
    assert [r.id for r in open_rows] == [open_id]


def test_double_close_raises_not_silent_overwrite(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    tid = store.insert_trade(_rec())
    store.close_trade(tid, exit_price=160.0,
                      exit_time=dt.datetime(2024, 1, 22, 14, 30), pnl=100.0)
    with pytest.raises(ValueError):
        store.close_trade(tid, exit_price=170.0,
                          exit_time=dt.datetime(2024, 1, 23, 14, 30), pnl=200.0)
    r = store.read_trades()[0]
    assert r.exit_price == 160.0  # first close preserved


def test_close_unknown_id_raises(tmp_path):
    store = PaperTradeStore(tmp_path / "t.sqlite")
    with pytest.raises(ValueError):
        store.close_trade(999, exit_price=1.0,
                          exit_time=dt.datetime(2024, 1, 1, 0, 0), pnl=0.0)
