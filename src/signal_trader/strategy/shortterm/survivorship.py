"""FREE synthetic-delisting survivorship stress test (Phase 4).

The honest problem this addresses: the ML OOS eval runs on a survivors-only
universe. yfinance returns no price history for a name that actually delisted or
went bankrupt, so every ticker we can load is, by construction, one that lived.
A clean fix needs a paid point-in-time delisted-price feed (CRSP / Sharadar /
Norgate) — flagged to Nico, out of scope for a free/local build.

What we CAN do for free is an adversarial stress test. For names that are in the
universe AND have a real, point-in-time delisting record (free SEC Form 25/25-NSE,
optional S&P 500 removal cross-check), the realized forward-return label is
overwritten with a pessimistic ``haircut`` (e.g. -0.60, or -1.0 for total loss)
on every decision bar whose label window opens on/after the delisting became
knowable. Re-running the SAME purged + embargoed walk-forward then answers: does
the ML-vs-baseline margin survive if the names that later left the listing are
punished instead of riding their (survivor) path?

Honesty boundaries (documented, not hidden):
  - This is a PARTIAL, conservative correction, not a true survivorship fix. It
    can only shade names that appear in the survivor universe AND in the free
    delisting list — a small subset. The bulk of delisted names are simply
    absent from the universe and cannot be reintroduced without paid prices.
  - Form 25 delistings mix voluntary delistings / M&A with bankruptcies, so a
    shaded name "left the listing" — it is not necessarily "bankrupt".
  - The haircut is a transparent assumption; report a sensitivity band rather
    than a single magic number.

Leakage discipline (mirrors ``consensus.py``): the haircut is keyed on
``delisted_known`` (when an outsider could know the delisting, i.e. the SEC
filing date), never the event date, and is applied only on/after that date — so
it injects no lookahead. Labels are overwritten in place, never fabricated or
dropped: a name with no record is returned byte-for-byte unchanged.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DelistingEvent:
    """A single point-in-time delisting record.

    ``delisted_known`` is the only date used (the date the delisting became
    knowable to an outsider — the SEC Form 25/25-NSE filing date), never an
    internal event date, so applying the haircut from it forward is leakage-free.
    """

    ticker: str
    delisted_known: dt.date


def apply_delisting_haircut(
    y: pd.Series,
    events: list[DelistingEvent],
    haircut: float,
) -> pd.Series:
    """Overwrite labels with ``haircut`` for ``(ticker, date)`` rows whose
    decision date is on/after the ticker's earliest knowable delisting.

    ``y`` is the forward-return label series indexed by ``(ticker, date)`` (as
    produced by ``build_dataset``). Returns a NEW series (input never mutated).
    Rows for tickers without a delisting record are left exactly as-is. When a
    ticker has several records, the EARLIEST ``delisted_known`` governs — shade
    as soon as the exit was knowable.
    """
    if not events or len(y) == 0:
        return y.copy()

    earliest_known: dict[str, pd.Timestamp] = {}
    for e in events:
        known = pd.Timestamp(e.delisted_known)
        cur = earliest_known.get(e.ticker)
        if cur is None or known < cur:
            earliest_known[e.ticker] = known

    out = y.copy()
    tickers = out.index.get_level_values("ticker")
    dates = out.index.get_level_values("date")
    mask = pd.Series(False, index=out.index)
    for ticker, known in earliest_known.items():
        mask |= (tickers == ticker) & (dates >= known)
    out[mask.to_numpy()] = haircut
    return out
