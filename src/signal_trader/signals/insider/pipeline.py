"""Compose source -> filters -> cluster -> priced, persisted signals.

Point-in-time end to end: price_at_known is the close on the last bar AT OR
BEFORE timestamp_known (never a later bar — that would be lookahead). A cluster
becomes a signal at its latest member's filing date. confidence scales with the
number of distinct insiders (more independent buyers = stronger). Nothing about
the trade date drives the recorded known date.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from signal_trader.signals.insider.cluster import cluster_purchases
from signal_trader.signals.insider.filters import keep_open_market_purchases
from signal_trader.signals.insider.opportunistic import keep_opportunistic
from signal_trader.sources.insider_source import InsiderSource
from signal_trader.store.signal_store import SignalRecord, SignalStore

SOURCE_NAME = "insider_form4"
_SIGNAL_TYPE = "insider_cluster_purchase"


def _price_at_or_before(close: pd.Series, known: dt.date) -> float | None:
    prior = close.loc[: pd.Timestamp(known)]
    if prior.empty:
        return None
    return float(prior.iloc[-1])


def build_insider_signals(
    source: InsiderSource,
    tickers: list[str],
    start: str,
    end: str,
    close_lookup: dict[str, pd.Series],
    store: SignalStore,
    window_days: int = 10,
    min_insiders: int = 3,
) -> int:
    """Fetch, filter, cluster, price, and persist insider signals. Returns count."""
    observations = source.fetch(tickers, start, end)
    purchases = keep_opportunistic(keep_open_market_purchases(observations))
    clusters = cluster_purchases(
        purchases, window_days=window_days, min_insiders=min_insiders
    )
    records: list[SignalRecord] = []
    for cluster in clusters:
        close = close_lookup.get(cluster.ticker)
        price = (
            _price_at_or_before(close, cluster.timestamp_known)
            if close is not None
            else None
        )
        earliest_event = min(m.timestamp_event for m in cluster.members)
        records.append(
            SignalRecord(
                ticker=cluster.ticker,
                source=SOURCE_NAME,
                signal_type=_SIGNAL_TYPE,
                direction="long",
                timestamp_event=earliest_event,
                timestamp_known=cluster.timestamp_known,
                price_at_known=price,
                raw_payload={
                    "accession_no": cluster.members[-1].accession_no,
                    "n_insiders": cluster.n_insiders,
                    "owners": sorted({m.reporting_owner for m in cluster.members}),
                },
                confidence=min(1.0, cluster.n_insiders / 5.0),
            )
        )
    store.insert_signals(records)
    return len(records)
