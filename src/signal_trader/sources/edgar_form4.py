"""edgartools-backed Form 4 source (edgartools 5.36.0).

The ONLY module importing `edgar`. It maps SEC Form 4 filings to
vendor-neutral InsiderObservation DTOs. Point-in-time: timestamp_known is the
FILING date (filing.filing_date), the first instant an outsider could act;
timestamp_event is the trade date inside the filing. set_identity satisfies
SEC fair access. In tests every edgartools symbol is mocked — no live call.

A filing that fails to parse is logged and SKIPPED, never silently dropped:
truncation that hides data loss is forbidden (Spec iron principles).
"""
from __future__ import annotations

import datetime as dt
import logging

from edgar import Company, set_identity

from signal_trader.sources.insider_source import InsiderObservation

_LOG = logging.getLogger(__name__)


def _to_date(value: object) -> dt.date:
    """Coerce edgartools date-ish values (str 'YYYY-MM-DD' or Timestamp)."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


class EdgarForm4Source:
    """Fetch Form 4 filings per ticker and flatten their trades to DTOs."""

    def __init__(self, identity: str | None):
        if not identity:
            raise ValueError(
                "SEC identity required (set SEC_IDENTITY in .env); refusing "
                "to contact SEC anonymously"
            )
        self._identity = identity

    def fetch(
        self, tickers: list[str], start: str, end: str
    ) -> list[InsiderObservation]:
        set_identity(self._identity)
        observations: list[InsiderObservation] = []
        for ticker in tickers:
            filings = Company(ticker).get_filings(
                form="4", filing_date=f"{start}:{end}"
            )
            for filing in filings:
                try:
                    observations.extend(self._observations_from_filing(ticker, filing))
                except Exception as exc:  # noqa: BLE001 - log + skip, never truncate silently
                    _LOG.warning(
                        "skip unparseable Form 4 %s for %s: %s",
                        getattr(filing, "accession_no", "?"),
                        ticker,
                        exc,
                    )
        return observations

    def _observations_from_filing(self, ticker, filing) -> list[InsiderObservation]:
        obj = filing.obj()
        known = _to_date(filing.filing_date)
        trades = obj.market_trades
        out: list[InsiderObservation] = []
        for row in trades.itertuples(index=False):
            out.append(
                InsiderObservation(
                    ticker=str(obj.issuer_ticker or ticker),
                    reporting_owner=str(obj.reporting_owner_name),
                    role=str(obj.position),
                    transaction_code=str(row.Code),
                    acquired_disposed=str(row.AcquiredDisposed),
                    shares=float(row.Shares),
                    price=float(row.Price),
                    timestamp_event=_to_date(row.Date),
                    timestamp_known=known,
                    is_10b5_1=bool(obj.has_10b5_1_plan),
                    accession_no=str(filing.accession_no),
                )
            )
        return out
