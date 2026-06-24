"""Opt-in point-in-time consensus feature for the ML experiment (Phase 4).

Counts how many *distinct* buyers (insiders / politicians / funds) had a buy
signal become knowable to an outsider in a backward window ending at the
decision bar ``t``.

Leakage is the whole point of this module, so two rules are absolute:

  - **As-of on ``timestamp_known``, never ``timestamp_event``.** A filing's event
    date is in the past, but it only becomes actionable on ``timestamp_known``;
    counting it before then is forward leakage. The join condition is strictly
    ``t - window_days < timestamp_known <= t``.
  - **No fabricated rows.** The feature is computed over the price dataset's
    EXISTING ``(ticker, date)`` index. A ``(ticker, date)`` with no qualifying
    signal gets an explicit 0 — we never invent a price/feature row to carry it,
    and we never drop a row for lacking signals.

"Distinct buyer" is keyed by ``(source, actor_id)``. The store has no first-class
person/fund id, so callers pass the most specific identifier available (e.g. the
filing accession number); identical re-filings therefore collapse to one buyer.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ConsensusSignal:
    """A single buy signal, reduced to what the as-of count needs.

    ``actor_id`` distinguishes distinct buyers within a source; ``timestamp_known``
    is the only date used (point-in-time), never the event date.
    """

    ticker: str
    timestamp_known: dt.date
    source: str
    actor_id: str


def consensus_buyers_known_le_t(
    index: pd.MultiIndex,
    signals: list[ConsensusSignal],
    window_days: int,
) -> pd.Series:
    """Distinct buyers per ``(ticker, date=t)`` with ``timestamp_known`` in
    ``(t - window_days, t]``.

    Returned Series is aligned 1:1 to ``index`` (same rows, same order), so a
    missing signal is an explicit 0 and no price row is fabricated or dropped.
    """
    feature_name = "consensus_buyers_known_le_t"
    if len(index) == 0:
        return pd.Series([], index=index, name=feature_name, dtype="int64")

    # Group distinct (source, actor) known-dates per ticker once, so each output
    # row is an O(signals_for_ticker) backward-window count — deterministic.
    by_ticker: dict[str, list[tuple[pd.Timestamp, tuple[str, str]]]] = {}
    for s in signals:
        known = pd.Timestamp(s.timestamp_known)
        by_ticker.setdefault(s.ticker, []).append((known, (s.source, s.actor_id)))

    window = pd.Timedelta(days=window_days)
    counts = []
    for ticker, t in index:
        t = pd.Timestamp(t)
        lo = t - window
        actors = {
            actor
            for known, actor in by_ticker.get(ticker, ())
            if lo < known <= t
        }
        counts.append(len(actors))
    return pd.Series(counts, index=index, name=feature_name, dtype="int64")
