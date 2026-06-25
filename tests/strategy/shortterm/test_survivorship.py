"""Tests for the FREE synthetic-delisting survivorship stress test (Phase 4).

The current OOS eval is survivors-only: yfinance serves no price path for a
truly delisted name, so every ticker in the universe is one that *survived*. This
module stress-tests that bias for free: for names we have a real, point-in-time
delisting record for, the realized forward-return label on/after the delisting
becomes knowable is overwritten with an adversarial haircut. If the ML-vs-baseline
margin survives that shading, the edge is not a pure survivorship artifact.

Leakage is the whole point, so the rules mirror ``consensus.py``:
  - The haircut is applied strictly on/after ``delisted_known`` (the SEC filing
    date) — never the event date, never earlier — so it injects no lookahead.
  - Labels are only overwritten, never fabricated or dropped: a row for a name
    with no delisting record is left exactly as-is.
These tests are offline and fixture-based (no network).
"""
import datetime as dt

import pandas as pd

from signal_trader.strategy.shortterm.survivorship import (
    DelistingEvent,
    apply_delisting_haircut,
    delisting_mask,
)


def _label_series(rows: dict[tuple[str, str], float]) -> pd.Series:
    idx = pd.MultiIndex.from_tuples(
        [(t, pd.Timestamp(d)) for (t, d) in rows], names=["ticker", "date"]
    )
    return pd.Series(list(rows.values()), index=idx, name="__label__", dtype=float)


def _event(ticker, known):
    return DelistingEvent(ticker=ticker, delisted_known=dt.date.fromisoformat(known))


def test_haircut_overwrites_labels_on_or_after_delisting_known():
    y = _label_series(
        {
            ("DEAD", "2024-01-05"): 0.10,  # before delisting -> untouched
            ("DEAD", "2024-01-10"): 0.20,  # on delisting -> haircut
            ("DEAD", "2024-01-15"): 0.30,  # after delisting -> haircut
        }
    )
    events = [_event("DEAD", "2024-01-10")]
    out = apply_delisting_haircut(y, events, haircut=-0.60)
    assert out.loc[("DEAD", pd.Timestamp("2024-01-05"))] == 0.10
    assert out.loc[("DEAD", pd.Timestamp("2024-01-10"))] == -0.60
    assert out.loc[("DEAD", pd.Timestamp("2024-01-15"))] == -0.60


def test_does_not_touch_names_without_a_delisting_record():
    y = _label_series(
        {
            ("ALIVE", "2024-01-10"): 0.05,
            ("ALIVE", "2024-02-10"): 0.07,
        }
    )
    out = apply_delisting_haircut(y, [_event("DEAD", "2024-01-10")], haircut=-1.0)
    pd.testing.assert_series_equal(out, y)


def test_returns_a_new_series_and_does_not_mutate_input():
    y = _label_series({("DEAD", "2024-01-10"): 0.20})
    before = y.copy()
    apply_delisting_haircut(y, [_event("DEAD", "2024-01-10")], haircut=-0.60)
    pd.testing.assert_series_equal(y, before)  # input untouched


def test_no_events_is_a_noop():
    y = _label_series({("DEAD", "2024-01-10"): 0.20})
    out = apply_delisting_haircut(y, [], haircut=-0.60)
    pd.testing.assert_series_equal(out, y)


def test_haircut_only_hits_the_matching_ticker():
    y = _label_series(
        {
            ("DEAD", "2024-01-15"): 0.30,
            ("ALIVE", "2024-01-15"): 0.30,  # same date, different ticker -> untouched
        }
    )
    out = apply_delisting_haircut(y, [_event("DEAD", "2024-01-10")], haircut=-0.60)
    assert out.loc[("DEAD", pd.Timestamp("2024-01-15"))] == -0.60
    assert out.loc[("ALIVE", pd.Timestamp("2024-01-15"))] == 0.30


def test_total_loss_haircut_is_minus_one():
    y = _label_series({("DEAD", "2024-01-15"): 0.30})
    out = apply_delisting_haircut(y, [_event("DEAD", "2024-01-10")], haircut=-1.0)
    assert out.loc[("DEAD", pd.Timestamp("2024-01-15"))] == -1.0


def test_mask_marks_only_decision_bars_on_or_after_delisting():
    idx = pd.MultiIndex.from_tuples(
        [("DEAD", pd.Timestamp("2024-01-05")),  # before -> False
         ("DEAD", pd.Timestamp("2024-01-10")),  # on -> True
         ("ALIVE", pd.Timestamp("2024-01-10"))],  # other ticker -> False
        names=["ticker", "date"],
    )
    mask = delisting_mask(idx, [_event("DEAD", "2024-01-10")])
    assert list(mask) == [False, True, False]


def test_mask_is_all_false_without_events():
    idx = pd.MultiIndex.from_tuples(
        [("DEAD", pd.Timestamp("2024-01-10"))], names=["ticker", "date"]
    )
    assert not delisting_mask(idx, []).any()


def test_earliest_delisting_wins_for_duplicate_ticker_events():
    """If a name appears twice (e.g. Form 25 then a later filing), the EARLIEST
    knowable delisting governs — shade as soon as the exit was knowable."""
    y = _label_series(
        {
            ("DEAD", "2024-01-08"): 0.10,  # before earliest -> untouched
            ("DEAD", "2024-01-12"): 0.20,  # after earliest -> haircut
        }
    )
    events = [_event("DEAD", "2024-01-20"), _event("DEAD", "2024-01-10")]
    out = apply_delisting_haircut(y, events, haircut=-0.60)
    assert out.loc[("DEAD", pd.Timestamp("2024-01-08"))] == 0.10
    assert out.loc[("DEAD", pd.Timestamp("2024-01-12"))] == -0.60
