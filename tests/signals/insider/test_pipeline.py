import datetime as dt

import pandas as pd

from signal_trader.signals.insider.pipeline import build_insider_signals
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
