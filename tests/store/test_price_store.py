import pandas as pd

from signal_trader.store.price_store import PriceBarStore


def _bars(ticker="AAPL"):
    return pd.DataFrame(
        {
            "ticker": [ticker, ticker],
            "date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1e6, 1.1e6],
        }
    )


def test_upsert_then_read_roundtrip(tmp_path):
    store = PriceBarStore(tmp_path / "t.sqlite")
    store.upsert_bars(_bars())
    out = store.read_bars(["AAPL"], "2020-01-01", "2020-01-10")
    assert len(out) == 2
    assert list(out.columns) == [
        "ticker", "date", "open", "high", "low", "close", "volume"
    ]


def test_upsert_is_idempotent_on_ticker_date(tmp_path):
    store = PriceBarStore(tmp_path / "t.sqlite")
    store.upsert_bars(_bars())
    store.upsert_bars(_bars())  # same primary key -> replace, not duplicate
    assert len(store.read_bars(["AAPL"], "2020-01-01", "2020-01-10")) == 2


def test_cached_tickers_reports_coverage(tmp_path):
    store = PriceBarStore(tmp_path / "t.sqlite")
    store.upsert_bars(_bars())
    assert store.cached_tickers() == {"AAPL"}


# Fix 3: fetched_at must be preserved on re-upsert
def test_upsert_preserves_fetched_at_on_re_upsert(tmp_path):
    import sqlite3

    store = PriceBarStore(tmp_path / "t.sqlite")
    store.upsert_bars(_bars())

    # Overwrite fetched_at with a known sentinel so timing cannot hide the bug
    sentinel = "2000-01-01 00:00:00"
    with sqlite3.connect(tmp_path / "t.sqlite") as con:
        con.execute("UPDATE price_bars SET fetched_at = ?", (sentinel,))

    # Re-upsert same (ticker, date) with a different close value
    updated = _bars().copy()
    updated["close"] = [999.0, 999.0]
    store.upsert_bars(updated)

    with sqlite3.connect(tmp_path / "t.sqlite") as con:
        new_fetched_at, new_close = con.execute(
            "SELECT fetched_at, close FROM price_bars WHERE ticker='AAPL' AND date='2020-01-02'"
        ).fetchone()

    assert new_close == 999.0, "close must be updated on re-upsert"
    assert new_fetched_at == sentinel, "fetched_at must not change on re-upsert"


# Fix 1 helper: covers() method
def test_covers_returns_true_only_when_range_is_fully_stored(tmp_path):
    store = PriceBarStore(tmp_path / "t.sqlite")
    # Nothing stored yet
    assert store.covers("AAPL", "2020-01-02", "2020-01-03") is False

    store.upsert_bars(_bars())  # dates: 2020-01-02, 2020-01-03
    assert store.covers("AAPL", "2020-01-02", "2020-01-03") is True
    # Wider end date not covered
    assert store.covers("AAPL", "2020-01-02", "2020-01-10") is False
    # Earlier start date not covered
    assert store.covers("AAPL", "2020-01-01", "2020-01-03") is False
