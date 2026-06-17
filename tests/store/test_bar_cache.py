import pandas as pd

from signal_trader.store.bar_cache import BarCache


def _bars(ticker="AAPL"):
    return pd.DataFrame(
        {
            "ticker": [ticker],
            "date": pd.to_datetime(["2020-01-02"]),
            "open": [100.0], "high": [101.0], "low": [99.0],
            "close": [100.5], "volume": [1e6],
        }
    )


def test_write_then_read_parquet_roundtrip(tmp_path):
    cache = BarCache(tmp_path)
    cache.write("AAPL", _bars())
    out = cache.read("AAPL")
    pd.testing.assert_frame_equal(out.reset_index(drop=True), _bars())


def test_has_reports_presence(tmp_path):
    cache = BarCache(tmp_path)
    assert cache.has("AAPL") is False
    cache.write("AAPL", _bars())
    assert cache.has("AAPL") is True
