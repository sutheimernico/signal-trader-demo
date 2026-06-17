"""Routine-vs-opportunistic classifier (Cohen/Malloy/Pomorski, JF 2012).

An (owner, ticker) who trades in the SAME calendar month for 3+ consecutive
years is "routine" — predictable, near-zero alpha — and those routine-month
trades are dropped. Everything else is "opportunistic" and kept. We classify
per (owner, ticker, month) using the trade date (timestamp_event); this is a
property of the trade pattern, not a point-in-time trading decision, so using
event time here is correct.
"""
from __future__ import annotations

from collections import defaultdict

from signal_trader.sources.insider_source import InsiderObservation

_ROUTINE_CONSECUTIVE_YEARS = 3


def _routine_keys(
    observations: list[InsiderObservation],
) -> set[tuple[str, str, int]]:
    years_by_key: dict[tuple[str, str, int], set[int]] = defaultdict(set)
    for o in observations:
        key = (o.reporting_owner, o.ticker, o.timestamp_event.month)
        years_by_key[key].add(o.timestamp_event.year)
    routine: set[tuple[str, str, int]] = set()
    for key, years in years_by_key.items():
        if _has_consecutive_run(years, _ROUTINE_CONSECUTIVE_YEARS):
            routine.add(key)
    return routine


def _has_consecutive_run(years: set[int], length: int) -> bool:
    return any(all((y + i) in years for i in range(length)) for y in years)


def keep_opportunistic(
    observations: list[InsiderObservation],
) -> list[InsiderObservation]:
    """Drop trades whose (owner, ticker, month) is a routine 3-year pattern."""
    routine = _routine_keys(observations)
    return [
        o
        for o in observations
        if (o.reporting_owner, o.ticker, o.timestamp_event.month) not in routine
    ]
