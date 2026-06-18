"""Compose 13F new-buy observations -> consensus-scored, persisted signals.

Each NEW long position from a famous fund is a vote. Multiple famous funds newly
buying the SAME ticker in the same window = consensus = a stronger signal (the
13F analogue of an insider cluster; the literature finds conviction+consensus
cloning is where the edge, if any, lives). Point-in-time: timestamp_known is the
LATEST contributing filing date; price_at_known is the close at/just before it,
never a future bar. Reuses the existing SignalStore / suggestion / scoring path.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from signal_trader.sources.superinvestor_13f import HoldingObservation
from signal_trader.store.signal_store import SignalRecord, SignalStore

SOURCE_NAME = "superinvestor_13f"
_SIGNAL_TYPE = "superinvestor_new_buy"


def _price_at_or_before(close: pd.Series, known: dt.date) -> float | None:
    prior = close.loc[: pd.Timestamp(known)]
    return float(prior.iloc[-1]) if not prior.empty else None


def build_13f_signals(
    source,
    fund_names: list[str],
    close_lookup: dict[str, pd.Series],
    store: SignalStore,
    roster_size: int = 3,
) -> int:
    """Fetch new 13F buys, consolidate by ticker (consensus), price, persist."""
    observations = source.fetch_new_long_positions(fund_names)
    return persist_13f_signals(observations, close_lookup, store, roster_size)


def persist_13f_signals(
    observations: list[HoldingObservation],
    close_lookup: dict[str, pd.Series],
    store: SignalStore,
    roster_size: int = 3,
) -> int:
    """Consolidate already-fetched observations by ticker, price, and persist."""
    by_ticker: dict[str, list[HoldingObservation]] = {}
    for o in observations:
        by_ticker.setdefault(o.ticker, []).append(o)

    records: list[SignalRecord] = []
    for ticker, obs in by_ticker.items():
        funds = sorted({o.fund for o in obs})
        known = max(o.timestamp_known for o in obs)
        event = min(o.timestamp_event for o in obs)
        close = close_lookup.get(ticker)
        price = _price_at_or_before(close, known) if close is not None else None
        records.append(
            SignalRecord(
                ticker=ticker,
                source=SOURCE_NAME,
                signal_type=_SIGNAL_TYPE,
                direction="long",
                timestamp_event=event,
                timestamp_known=known,
                price_at_known=price,
                raw_payload={
                    "accession_no": sorted(o.accession_no for o in obs)[-1],
                    "n_insiders": len(funds),       # # funds (reuses dashboard field)
                    "owners": funds,                # fund names (the "who")
                    "sources": sorted({o.url for o in obs if o.url}),
                },
                confidence=min(1.0, len(funds) / roster_size),
            )
        )
    store.insert_signals(records)
    return len(records)
