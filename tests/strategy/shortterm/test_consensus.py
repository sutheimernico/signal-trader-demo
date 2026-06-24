"""Tests for the opt-in insider/congress/fund consensus feature.

The whole point of this feature is the leakage surface: the as-of join must use
``timestamp_known`` (when an outsider could act), never ``timestamp_event``, and
must never fabricate a price row to carry a zero. These tests are offline and
fixture-based.
"""
import datetime as dt

import pandas as pd

from signal_trader.strategy.shortterm.consensus import (
    ConsensusSignal,
    consensus_buyers_known_le_t,
)


def _bdays(start, n):
    return pd.date_range(start, periods=n, freq="B")


def _sig(ticker, known, source="insider_form4", actor="a"):
    return ConsensusSignal(
        ticker=ticker, timestamp_known=dt.date.fromisoformat(known), source=source, actor_id=actor
    )


def test_counts_distinct_buyers_with_known_on_or_before_t_in_window():
    idx = pd.MultiIndex.from_tuples(
        [("AAA", pd.Timestamp("2024-01-10"))], names=["ticker", "date"]
    )
    signals = [
        _sig("AAA", "2024-01-05", source="insider_form4", actor="x"),
        _sig("AAA", "2024-01-08", source="congress_house", actor="y"),
        _sig("AAA", "2024-01-08", source="congress_house", actor="y"),  # dup -> 1
    ]
    out = consensus_buyers_known_le_t(idx, signals, window_days=30)
    assert out.loc[("AAA", pd.Timestamp("2024-01-10"))] == 2  # x and y, dup collapsed


def test_signal_known_after_t_does_not_affect_feature_at_t():
    """As-of leak guard: a signal whose timestamp_known is t+1 MUST NOT count at t."""
    t = pd.Timestamp("2024-01-10")
    idx = pd.MultiIndex.from_tuples([("AAA", t)], names=["ticker", "date"])
    future = [_sig("AAA", "2024-01-11", actor="future")]  # known = t+1
    out = consensus_buyers_known_le_t(idx, future, window_days=30)
    assert out.loc[("AAA", t)] == 0


def test_same_day_known_equal_t_counts():
    """timestamp_known == t is knowable at t (boundary is inclusive)."""
    t = pd.Timestamp("2024-01-10")
    idx = pd.MultiIndex.from_tuples([("AAA", t)], names=["ticker", "date"])
    out = consensus_buyers_known_le_t(idx, [_sig("AAA", "2024-01-10", actor="z")], window_days=30)
    assert out.loc[("AAA", t)] == 1


def test_signal_older_than_window_is_excluded():
    t = pd.Timestamp("2024-03-01")
    idx = pd.MultiIndex.from_tuples([("AAA", t)], names=["ticker", "date"])
    signals = [
        _sig("AAA", "2024-02-25", actor="recent"),   # within 30d
        _sig("AAA", "2024-01-01", actor="stale"),     # older than 30d -> excluded
    ]
    out = consensus_buyers_known_le_t(idx, signals, window_days=30)
    assert out.loc[("AAA", t)] == 1


def test_missing_signals_yield_zero_not_dropped_or_fabricated():
    """No signals for a (ticker, date) -> feature 0, and NO row is dropped or added."""
    idx = pd.MultiIndex.from_tuples(
        [("AAA", pd.Timestamp("2024-01-10")), ("BBB", pd.Timestamp("2024-01-10"))],
        names=["ticker", "date"],
    )
    out = consensus_buyers_known_le_t(idx, [_sig("AAA", "2024-01-09", actor="x")], window_days=30)
    assert list(out.index) == list(idx)         # same rows, none dropped, none added
    assert out.loc[("AAA", pd.Timestamp("2024-01-10"))] == 1
    assert out.loc[("BBB", pd.Timestamp("2024-01-10"))] == 0


def test_empty_signals_yield_all_zero_over_existing_rows():
    idx = pd.MultiIndex.from_tuples(
        [("AAA", pd.Timestamp("2024-01-10")), ("AAA", pd.Timestamp("2024-01-11"))],
        names=["ticker", "date"],
    )
    out = consensus_buyers_known_le_t(idx, [], window_days=30)
    assert (out == 0).all()
    assert list(out.index) == list(idx)


def test_ticker_scoped_no_cross_ticker_leak():
    t = pd.Timestamp("2024-01-10")
    idx = pd.MultiIndex.from_tuples([("AAA", t), ("BBB", t)], names=["ticker", "date"])
    signals = [_sig("AAA", "2024-01-09", actor="x"), _sig("AAA", "2024-01-08", actor="y")]
    out = consensus_buyers_known_le_t(idx, signals, window_days=30)
    assert out.loc[("AAA", t)] == 2
    assert out.loc[("BBB", t)] == 0  # AAA signals never bleed into BBB


def test_deterministic_join_same_inputs_same_output():
    idx = pd.MultiIndex.from_tuples(
        [("AAA", d) for d in _bdays("2024-01-10", 5)], names=["ticker", "date"]
    )
    signals = [
        _sig("AAA", "2024-01-09", source="insider_form4", actor="x"),
        _sig("AAA", "2024-01-11", source="congress_house", actor="y"),
        _sig("AAA", "2024-01-12", source="superinvestor_13f", actor="z"),
    ]
    a = consensus_buyers_known_le_t(idx, list(reversed(signals)), window_days=30)
    b = consensus_buyers_known_le_t(idx, signals, window_days=30)
    pd.testing.assert_series_equal(a, b)
