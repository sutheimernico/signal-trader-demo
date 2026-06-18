"""Routine-vs-opportunistic classifier (Cohen/Malloy/Pomorski, JF 2012).

An (owner, ticker) who trades in the SAME calendar month for 3+ consecutive
years is "routine" — predictable, near-zero alpha — and those routine-month
trades are dropped. Everything else is "opportunistic" and kept. We classify
per (owner, ticker, month) using the trade date (timestamp_event); this is a
property of the trade pattern, not a point-in-time trading decision, so using
event time here is correct.

Precondition: ``observations`` should span at least 3 years of prior history
per insider so that routine calendar-month patterns can be reliably identified.
If the input window is shorter than ~1095 days, routine traders will silently
pass through (not enough history to classify them). A WARNING is emitted when
this precondition is not met.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from signal_trader.sources.insider_source import InsiderObservation

_ROUTINE_CONSECUTIVE_YEARS = 3
_MIN_WINDOW_DAYS = 1095  # ≈ 3 years

_LOG = logging.getLogger(__name__)


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
    """Drop trades whose (owner, ticker, month) is a routine 3-year pattern.

    Requires full multi-year insider history (>= 3 years) in ``observations``
    for reliable routine classification. Emits a WARNING when the input span
    is shorter than 1095 days.
    """
    if observations:
        dates = [o.timestamp_event for o in observations]
        span_days = (max(dates) - min(dates)).days
        if span_days < _MIN_WINDOW_DAYS:
            _LOG.warning(
                "routine classification may be unreliable: observation window "
                "spans only %d days (< %d required for 3-year pattern detection)",
                span_days,
                _MIN_WINDOW_DAYS,
            )
    routine = _routine_keys(observations)
    return [
        o
        for o in observations
        if (o.reporting_owner, o.ticker, o.timestamp_event.month) not in routine
    ]
