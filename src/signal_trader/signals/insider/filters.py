"""Signal-vs-noise filters for insider observations (Spec §12).

Keep only what is informative for an outsider: transaction code "P"
(open-market purchase), genuinely acquired (AcquiredDisposed == "A"), and NOT
executed under a 10b5-1 plan (those are pre-scheduled, near-zero signal).
Sales, option exercises (M), grants/awards (A-code), vesting, and dispositions
are dropped — purchases inform, sales are noise (Cohen/Malloy/Pomorski).
"""
from __future__ import annotations

from signal_trader.sources.insider_source import InsiderObservation

_OPEN_MARKET_PURCHASE = "P"
_ACQUIRED = "A"


def keep_open_market_purchases(
    observations: list[InsiderObservation],
) -> list[InsiderObservation]:
    """Return only open-market, non-10b5-1, acquired purchases."""
    return [
        o
        for o in observations
        if o.transaction_code == _OPEN_MARKET_PURCHASE
        and o.acquired_disposed == _ACQUIRED
        and not o.is_10b5_1
    ]
