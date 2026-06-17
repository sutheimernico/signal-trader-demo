import pandas as pd
import pytest

from signal_trader.store.cache_service import CacheService


class FakeProvider:
    """Returns bars on the first and last business day of [start, end] per ticker.

    Covers the full requested range in the store so that a repeat call with the
    same [start, end] is correctly identified as already covered.
    """

    def __init__(self):
        self.calls = []

    def fetch(self, tickers, start, end):
        self.calls.append(list(tickers))
        # Use first and last business day so stored min <= start and max >= end
        dates = [pd.Timestamp(start), pd.Timestamp(end)]
        frames = []
        for t in tickers:
            frames.append(pd.DataFrame({
                "ticker": [t, t],
                "date": dates,
                "open": [1.0, 1.0],
                "high": [1.0, 1.0],
                "low": [1.0, 1.0],
                "close": [1.0, 1.0],
                "volume": [1.0, 1.0],
            }))
        return pd.concat(frames, ignore_index=True)


class RangeFakeProvider:
    """Returns one bar per trading day in [start, end] for each requested ticker."""

    def __init__(self):
        self.calls: list[tuple[list[str], str, str]] = []

    def fetch(self, tickers, start, end):
        self.calls.append((list(tickers), start, end))
        dates = pd.date_range(start, end, freq="B")  # business days
        frames = []
        for t in tickers:
            frames.append(pd.DataFrame({
                "ticker": t,
                "date": dates,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 2.0,
                "volume": 1.0,
            }))
        if not frames:
            cols = ["ticker", "date", "open", "high", "low", "close", "volume"]
            return pd.DataFrame(columns=cols)
        return pd.concat(frames, ignore_index=True)


# ── existing tests (kept intact) ──────────────────────────────────────────────

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


# ── Fix 1: range-aware caching ────────────────────────────────────────────────

def test_backfill_refetches_when_wider_range_requested(tmp_path):
    """
    Backfill a narrow range, then a wider range.
    The provider must be called again for the wider range,
    and load_close_matrix over the wider range must include the extra rows.
    """
    provider = RangeFakeProvider()
    svc = CacheService(provider, tmp_path / "bars", tmp_path / "t.sqlite")

    # Narrow first fill: only 2020-01-06 → 2020-01-10 (5 business days)
    svc.backfill(["AAPL"], "2020-01-06", "2020-01-10")
    assert len(provider.calls) == 1

    # Wider fill: 2020-01-02 → 2020-01-31 — must re-fetch
    svc.backfill(["AAPL"], "2020-01-02", "2020-01-31")
    assert len(provider.calls) == 2, "provider must be called again for the wider range"

    # Second identical wide fill — must NOT re-fetch
    svc.backfill(["AAPL"], "2020-01-02", "2020-01-31")
    assert len(provider.calls) == 2, "identical full-range repeat must not re-fetch"

    # The close matrix over the wider range must span from 2020-01-02
    close = svc.load_close_matrix(["AAPL"], "2020-01-02", "2020-01-31")
    assert close.index.min() <= pd.Timestamp("2020-01-02")
    assert close.index.max() >= pd.Timestamp("2020-01-31")


# ── Fix 2: no-silent truncation ───────────────────────────────────────────────

def test_load_close_matrix_raises_for_uncached_ticker(tmp_path):
    """load_close_matrix must raise ValueError naming tickers absent from the store."""
    provider = FakeProvider()
    svc = CacheService(provider, tmp_path / "bars", tmp_path / "t.sqlite")
    svc.backfill(["AAPL"], "2020-01-01", "2020-01-10")

    with pytest.raises(ValueError, match="MSFT"):
        svc.load_close_matrix(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")


def test_load_close_matrix_succeeds_when_all_tickers_cached(tmp_path):
    """No exception when every requested ticker is present in the store."""
    provider = FakeProvider()
    svc = CacheService(provider, tmp_path / "bars", tmp_path / "t.sqlite")
    svc.backfill(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    close = svc.load_close_matrix(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    assert set(close.columns) == {"AAPL", "MSFT"}
