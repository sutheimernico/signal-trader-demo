"""Consolidate House congressional PURCHASE observations into consensus signals.

Like the 13F path: dedup by (member, ticker, transaction_date), then group by
ticker — multiple DISTINCT members buying the same ticker = consensus = stronger.
Point-in-time: timestamp_known is the LATEST House filing date among contributors.
Reuses the SignalStore / suggestion / scoring path. Source = "congress_house".
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from signal_trader.store.signal_store import SignalRecord, SignalStore

SOURCE_NAME = "congress_house"
_SIGNAL_TYPE = "congress_purchase"


def _price_at_or_before(close: pd.Series, known: dt.date) -> float | None:
    prior = close.loc[: pd.Timestamp(known)]
    return float(prior.iloc[-1]) if not prior.empty else None


def persist_congress_signals(
    observations,
    close_lookup: dict[str, pd.Series],
    store: SignalStore,
    roster_size: int = 3,
) -> int:
    """Dedup, consolidate by ticker (distinct members = consensus), price, persist."""
    seen: set = set()
    by_ticker: dict[str, list] = {}
    for o in observations:
        key = (o.member, o.ticker, o.transaction_date)
        if key in seen:
            continue
        seen.add(key)
        by_ticker.setdefault(o.ticker, []).append(o)

    records: list[SignalRecord] = []
    for ticker, obs in by_ticker.items():
        members = sorted({o.member for o in obs})
        known = max(o.timestamp_known for o in obs)
        event = min(o.transaction_date for o in obs)
        close = close_lookup.get(ticker)
        price = _price_at_or_before(close, known) if close is not None else None
        records.append(SignalRecord(
            ticker=ticker, source=SOURCE_NAME, signal_type=_SIGNAL_TYPE,
            direction="long", timestamp_event=event, timestamp_known=known,
            price_at_known=price,
            raw_payload={
                "accession_no": sorted(o.doc_id for o in obs)[-1],
                "n_insiders": len(members),
                "owners": members,
                "sources": sorted({o.url for o in obs if o.url}),
            },
            confidence=min(1.0, len(members) / roster_size),
        ))
    store.insert_signals(records)
    return len(records)
