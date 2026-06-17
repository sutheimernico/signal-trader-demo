import pandas as pd

from signal_trader.store.cache_service import CacheService


class FakeProvider:
    def __init__(self):
        self.calls = []

    def fetch(self, tickers, start, end):
        self.calls.append(list(tickers))
        frames = []
        for t in tickers:
            frames.append(pd.DataFrame({
                "ticker": [t], "date": pd.to_datetime(["2020-01-02"]),
                "open": [1.0], "high": [1.0], "low": [1.0],
                "close": [1.0], "volume": [1.0],
            }))
        return pd.concat(frames, ignore_index=True)


def test_backfill_fetches_missing_only(tmp_path):
    provider = FakeProvider()
    svc = CacheService(provider, tmp_path / "bars", tmp_path / "t.sqlite")
    svc.backfill(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    assert sorted(provider.calls[0]) == ["AAPL", "MSFT"]

    svc.backfill(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")  # already cached
    assert len(provider.calls) == 1  # no second fetch


def test_load_close_matrix_returns_wide_frame(tmp_path):
    provider = FakeProvider()
    svc = CacheService(provider, tmp_path / "bars", tmp_path / "t.sqlite")
    svc.backfill(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    close = svc.load_close_matrix(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    assert list(close.columns) == ["AAPL", "MSFT"]
    assert close.index.name == "date"
