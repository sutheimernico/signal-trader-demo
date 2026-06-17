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
