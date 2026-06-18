import datetime as dt

import pandas as pd
import pytest

from signal_trader.signals.insider.pipeline import _price_at_or_before, build_insider_signals
from signal_trader.sources.insider_source import InsiderObservation
from signal_trader.store.signal_store import SignalStore


class FakeSource:
    def __init__(self, obs):
        self._obs = obs

    def fetch(self, tickers, start, end):
        return [o for o in self._obs if o.ticker in tickers]


def _obs(owner, ticker, day, code="P", acq="A", plan=False, price=10.0):
    return InsiderObservation(
        ticker=ticker, reporting_owner=owner, role="Director",
        transaction_code=code, acquired_disposed=acq, shares=100.0, price=price,
        timestamp_event=dt.date(2024, 1, day),
        timestamp_known=dt.date(2024, 1, day + 2),
        is_10b5_1=plan, accession_no=f"{owner}-{day}",
    )


def _close_lookup():
    # ticker -> Series of close indexed by date
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    return {"AAPL": pd.Series(range(100, 160), index=idx, dtype=float)}


def test_pipeline_keeps_only_clustered_purchases_and_prices_them(tmp_path):
    source = FakeSource([
        _obs("A", "AAPL", 1), _obs("B", "AAPL", 2), _obs("C", "AAPL", 3),
        _obs("D", "AAPL", 4, code="S"),  # sale -> dropped
        _obs("E", "AAPL", 5, plan=True),  # 10b5-1 -> dropped
    ])
    store = SignalStore(tmp_path / "t.sqlite")
    n = build_insider_signals(
        source, ["AAPL"], "2024-01-01", "2024-01-31",
        close_lookup=_close_lookup(), store=store,
        window_days=10, min_insiders=3,
    )
    rows = store.read_signals(source="insider_form4")
    assert n == len(rows) >= 1
    r = rows[0]
    assert r.direction == "long"
    assert r.signal_type == "insider_cluster_purchase"
    # price_at_known taken from the bar on/just before timestamp_known
    assert r.price_at_known is not None


def test_no_signal_when_below_cluster_threshold(tmp_path):
    source = FakeSource([_obs("A", "AAPL", 1), _obs("B", "AAPL", 2)])
    store = SignalStore(tmp_path / "t.sqlite")
    n = build_insider_signals(
        source, ["AAPL"], "2024-01-01", "2024-01-31",
        close_lookup=_close_lookup(), store=store,
        window_days=10, min_insiders=3,
    )
    assert n == 0
    assert store.read_signals(source="insider_form4") == []


def test_price_at_known_uses_last_bar_at_or_before_known_not_future(tmp_path):
    # known is a weekend/gap day -> must use prior bar, never a later one
    source = FakeSource([_obs("A", "AAPL", 1), _obs("B", "AAPL", 2), _obs("C", "AAPL", 3)])
    store = SignalStore(tmp_path / "t.sqlite")
    build_insider_signals(
        source, ["AAPL"], "2024-01-01", "2024-01-31",
        close_lookup=_close_lookup(), store=store, window_days=10, min_insiders=3,
    )
    r = store.read_signals(source="insider_form4")[0]
    known_idx = pd.Timestamp(r.timestamp_known)
    series = _close_lookup()["AAPL"]
    expected = float(series.loc[:known_idx].iloc[-1])
    assert r.price_at_known == expected


# Fix 2: price lookup guard
def test_price_at_or_before_non_datetimeindex_raises():
    """Non-DatetimeIndex Series must raise AssertionError immediately."""
    bad = pd.Series([100.0, 101.0], index=[0, 1])
    with pytest.raises(AssertionError, match="DatetimeIndex"):
        _price_at_or_before(bad, dt.date(2024, 1, 5))


# Fix 6: small-cap tilt parameter
def test_max_price_filters_observations_before_clustering(tmp_path):
    """With max_price set, only sub-threshold observations reach the cluster stage."""
    source = FakeSource([
        # Three cheap buyers -> should cluster
        _obs("A", "AAPL", 1, price=5.0),
        _obs("B", "AAPL", 2, price=5.0),
        _obs("C", "AAPL", 3, price=5.0),
        # Three expensive buyers for MSFT -> should be filtered out
        _obs("A", "MSFT", 1, price=500.0),
        _obs("B", "MSFT", 2, price=500.0),
        _obs("C", "MSFT", 3, price=500.0),
    ])
    store = SignalStore(tmp_path / "t.sqlite")
    build_insider_signals(
        source, ["AAPL", "MSFT"], "2024-01-01", "2024-01-31",
        close_lookup=_close_lookup(), store=store,
        window_days=10, min_insiders=3, max_price=50.0,
    )
    rows = store.read_signals(source="insider_form4")
    tickers = {r.ticker for r in rows}
    assert "AAPL" in tickers
    assert "MSFT" not in tickers


def test_no_max_price_passes_all_observations_through(tmp_path):
    """Default max_price=None: no small-cap filter applied, both tickers can cluster."""
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    close = {
        "AAPL": pd.Series(range(100, 160), index=idx, dtype=float),
        "MSFT": pd.Series(range(200, 260), index=idx, dtype=float),
    }
    source = FakeSource([
        _obs("A", "AAPL", 1, price=5.0),
        _obs("B", "AAPL", 2, price=5.0),
        _obs("C", "AAPL", 3, price=5.0),
        _obs("A", "MSFT", 1, price=500.0),
        _obs("B", "MSFT", 2, price=500.0),
        _obs("C", "MSFT", 3, price=500.0),
    ])
    store = SignalStore(tmp_path / "t.sqlite")
    build_insider_signals(
        source, ["AAPL", "MSFT"], "2024-01-01", "2024-01-31",
        close_lookup=close, store=store,
        window_days=10, min_insiders=3,
    )
    tickers = {r.ticker for r in store.read_signals(source="insider_form4")}
    assert "AAPL" in tickers
    assert "MSFT" in tickers
