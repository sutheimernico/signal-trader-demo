"""Vendor-neutral insider-source seam (analogous to PriceProvider).

InsiderObservation is the single contract every downstream filter, store,
and scorer consumes — edgartools types never leak past the adapter. The
point-in-time invariant lives here: timestamp_known (filing date) is when an
OUTSIDER could act; timestamp_event (trade date) is private until filed and
must never drive a trade. We enforce known >= event at construction.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class InsiderObservation:
    ticker: str
    reporting_owner: str
    role: str
    transaction_code: str
    acquired_disposed: str  # "A" acquired / "D" disposed
    shares: float
    price: float
    timestamp_event: dt.date  # trade date (private until filed)
    timestamp_known: dt.date  # filing date (point-in-time)
    is_10b5_1: bool
    accession_no: str
    url: str = ""  # public SEC EDGAR filing URL (source of record), if known

    def __post_init__(self) -> None:
        if self.timestamp_known < self.timestamp_event:
            raise ValueError(
                "timestamp_known (filing) must not predate timestamp_event (trade)"
            )

    @property
    def notional(self) -> float:
        return self.shares * self.price


@runtime_checkable
class InsiderSource(Protocol):
    def fetch(
        self, tickers: list[str], start: str, end: str
    ) -> list[InsiderObservation]:
        """Return insider observations whose FILING date is in [start, end]."""
        ...
