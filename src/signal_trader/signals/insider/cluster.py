"""Cluster detection + optional small-cap tilt (Spec §12).

A cluster is >= min_insiders DISTINCT reporting owners buying the same ticker
within a rolling window measured in FILING (known) days — the point-in-time
horizon an outsider observes. The cluster's known date is the LATEST filing in
the window: the cluster is not 'known' until its final member has filed, so
trading earlier would be lookahead.

Small-cap tilt: a deliberately crude price proxy (Spec keeps it optional). We
have no free survivorship-clean market-cap feed, so a low share price is used
as a stand-in and documented as such — never presented as true market cap.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from signal_trader.sources.insider_source import InsiderObservation


@dataclass(frozen=True)
class InsiderCluster:
    ticker: str
    n_insiders: int
    timestamp_known: dt.date  # latest filing in the window (PIT)
    members: tuple[InsiderObservation, ...]


def cluster_purchases(
    observations: list[InsiderObservation],
    window_days: int = 10,
    min_insiders: int = 3,
) -> list[InsiderCluster]:
    """Detect, per ticker, the first window with >= min_insiders distinct owners."""
    clusters: list[InsiderCluster] = []
    by_ticker: dict[str, list[InsiderObservation]] = {}
    for o in observations:
        by_ticker.setdefault(o.ticker, []).append(o)
    for ticker, obs in by_ticker.items():
        obs = sorted(obs, key=lambda o: o.timestamp_known)
        for i, anchor in enumerate(obs):
            window = [
                o
                for o in obs[i:]
                if (o.timestamp_known - anchor.timestamp_known).days <= window_days
            ]
            owners = {o.reporting_owner for o in window}
            if len(owners) >= min_insiders:
                clusters.append(
                    InsiderCluster(
                        ticker=ticker,
                        n_insiders=len(owners),
                        timestamp_known=max(o.timestamp_known for o in window),
                        members=tuple(window),
                    )
                )
                break
    return clusters


def keep_small_cap(
    observations: list[InsiderObservation], max_price: float
) -> list[InsiderObservation]:
    """Crude small-cap tilt by share price (proxy only, not market cap)."""
    return [o for o in observations if o.price <= max_price]
