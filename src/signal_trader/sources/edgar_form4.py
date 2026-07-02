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

from edgar import Company, get_filings, set_identity

from signal_trader.sources.insider_source import InsiderObservation

_LOG = logging.getLogger(__name__)


def _to_date(value: object) -> dt.date:
    """Coerce edgartools date-ish values (str 'YYYY-MM-DD' or Timestamp)."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


_TICKER_PLACEHOLDERS = {"", "N/A", "NA", "NONE", "NULL"}


def _issuer_ticker(obj, fallback: str) -> str:
    """Normalized issuer ticker; "" for placeholders/unresolvable (untradeable).

    Strips internal whitespace ('N O G' -> 'NOG') and rejects placeholders like
    'N/A' that edgartools returns when no ticker resolved.
    """
    issuer = getattr(obj, "issuer", None)
    raw = getattr(issuer, "ticker", None) or fallback
    t = str(raw).strip().replace(" ", "").upper()
    return "" if t in _TICKER_PLACEHOLDERS else t


def _is_10b5_1(obj) -> bool:
    """Detect a 10b5-1 plan from footnote text (edgartools has no direct flag).

    Real Form4 objects expose footnotes (id -> text) rather than a boolean
    has_10b5_1_plan. A filing whose footnotes mention Rule 10b5-1 is treated as
    plan-driven (pre-scheduled, near-zero signal) and later dropped by the noise
    filter. Conservative: any 10b5-1 mention marks the whole filing.
    """
    foot = getattr(obj, "footnotes", None)
    if not foot:
        return False
    # edgartools' Footnotes renders its id->text mapping via str(); searching the
    # rendered text avoids its non-standard iteration (keyed by string ids).
    text = str(foot).lower()
    return "10b5-1" in text or "10b5 1" in text


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
                except Exception as exc:  # log + skip, never truncate silently
                    _LOG.warning(
                        "skip unparseable Form 4 %s for %s: %s",
                        getattr(filing, "accession_no", "?"),
                        ticker,
                        exc,
                    )
        return observations

    def fetch_market_wide(
        self,
        start: str,
        end: str,
        min_filings: int = 3,
        max_candidates: int = 300,
        max_filings: int = 25,
    ) -> list[InsiderObservation]:
        """Scan ALL Form 4 filings in [start, end] and parse candidate issuers.

        edgartools indexes Form 4 by issuer CIK, so insider activity clusters as
        many filings under one CIK. We keep issuers with `min_filings`..`max_filings`
        filings: the floor catches small/young companies (a 3-insider buy cluster
        is only ~3 filings — these are exactly the early names Nico wants), the
        CEILING drops mega-caps whose 30+ filings are routine grants/sells (noise,
        not buy clusters). Smaller-count issuers are prioritized (more likely a
        focused buy cluster than a big company's routine churn). Downstream
        purchase/cluster filters still decide what becomes a signal; nothing is
        silently truncated.
        """
        set_identity(self._identity)
        filings = get_filings(form="4", filing_date=f"{start}:{end}")
        df = filings.to_pandas()
        counts = df.groupby("cik").size()
        eligible = counts[(counts >= min_filings) & (counts <= max_filings)]
        # ascending: favor focused small-cap clusters over big routine churn
        eligible = eligible.sort_values(ascending=True)
        candidate_ciks = set(eligible.head(max_candidates).index)
        skipped = len(eligible) - len(candidate_ciks)
        if skipped > 0:
            _LOG.warning(
                "market scan: %d issuers in [%d,%d] filings, parsing %d, skipping %d",
                len(eligible), min_filings, max_filings, len(candidate_ciks), skipped,
            )
        observations: list[InsiderObservation] = []
        for filing in filings:
            if getattr(filing, "cik", None) not in candidate_ciks:
                continue
            try:
                # Drop rows without a resolvable issuer ticker — untradeable,
                # would surface as a junk "N/A" suggestion otherwise.
                observations.extend(
                    o for o in self._observations_from_filing("", filing) if o.ticker
                )
            except Exception as exc:  # log + skip, never truncate silently
                _LOG.warning(
                    "skip unparseable Form 4 %s: %s",
                    getattr(filing, "accession_no", "?"), exc,
                )
        return observations

    def _observations_from_filing(self, ticker, filing) -> list[InsiderObservation]:
        obj = filing.obj()
        known = _to_date(filing.filing_date)
        trades = obj.market_trades
        # None or empty DataFrame means no open-market trades — normal, not error.
        if trades is None or trades.empty:
            return []
        issuer_ticker = _issuer_ticker(obj, ticker)
        owner = str(obj.insider_name)
        role = str(obj.position)
        is_plan = _is_10b5_1(obj)
        # Human-readable EDGAR index page = the source of record for this filing.
        url = str(getattr(filing, "homepage_url", "") or getattr(filing, "filing_url", "") or "")
        out: list[InsiderObservation] = []
        for row in trades.itertuples(index=False):
            out.append(
                InsiderObservation(
                    ticker=issuer_ticker,
                    reporting_owner=owner,
                    role=role,
                    transaction_code=str(row.Code),
                    acquired_disposed=str(row.AcquiredDisposed),
                    shares=float(row.Shares),
                    price=float(row.Price),
                    timestamp_event=_to_date(row.Date),
                    timestamp_known=known,
                    is_10b5_1=is_plan,
                    accession_no=str(filing.accession_no),
                    url=url,
                )
            )
        return out
