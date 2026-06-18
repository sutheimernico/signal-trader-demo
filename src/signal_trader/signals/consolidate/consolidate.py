"""Per-ticker consolidation of contributing signals (Spec §9 Suggestion).

consolidated_score = sum of contributing signal confidences; latest_known is
the most recent point-in-time date among contributors (the earliest an outsider
could act on the consolidated view). Pure aggregation, no price lookups.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from signal_trader.store.signal_store import StoredSignal


@dataclass(frozen=True)
class ConsolidatedSignal:
    ticker: str
    consolidated_score: float
    n_contributing: int
    latest_known: dt.date


def consolidate_per_ticker(
    signals: list[StoredSignal],
) -> dict[str, ConsolidatedSignal]:
    by_ticker: dict[str, list[StoredSignal]] = {}
    for s in signals:
        by_ticker.setdefault(s.ticker, []).append(s)
    out: dict[str, ConsolidatedSignal] = {}
    for ticker, group in by_ticker.items():
        out[ticker] = ConsolidatedSignal(
            ticker=ticker,
            consolidated_score=sum(s.confidence for s in group),
            n_contributing=len(group),
            latest_known=max(s.timestamp_known for s in group),
        )
    return out
