"""Free, point-in-time US House congressional stock-trade source (STOCK Act).

The House Clerk publishes a yearly bulk ZIP (FD.xml) listing every financial
disclosure with its FILING DATE — the date it became public, our point-in-time
`timestamp_known`. Periodic Transaction Reports (FilingType "P") carry the stock
trades; the per-filing PTR PDF holds the tickers + buy/sell + transaction date.
We keep PURCHASES only. Electronic PTRs parse cleanly; scanned/handwritten ones
have no text and are logged + skipped (never silently dropped).

Free and current (no API key, unlike Senate efdsearch which blocks bots). The
~30-45 day STOCK Act disclosure lag is real and surfaced honestly by the harness.
"""
from __future__ import annotations

import datetime as dt
import io
import logging
import re
import urllib.request
import zipfile
from dataclasses import dataclass

from pypdf import PdfReader

_LOG = logging.getLogger(__name__)
_UA = {"User-Agent": "signal-trader research (contact via SEC_IDENTITY)"}
_FD_ZIP = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{yr}FD.zip"
_PTR_PDF = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{yr}/{doc}.pdf"

# Ticker in parentheses, e.g. "Amazon.com, Inc. - Common Stock (AMZN) [ST]".
_TICKER_RE = re.compile(r"\(([A-Z]{1,5})\)\s*\[ST\]")
# A US-style date mm/dd/yyyy.
_DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")


@dataclass(frozen=True)
class CongressObservation:
    member: str
    ticker: str
    transaction_date: dt.date
    timestamp_known: dt.date  # House filing date (point-in-time)
    amount: str
    url: str
    doc_id: str

    def __post_init__(self) -> None:
        if self.timestamp_known < self.transaction_date:
            raise ValueError("filing date must not predate the transaction date")


def _to_date(mmddyyyy: str) -> dt.date:
    return dt.datetime.strptime(mmddyyyy, "%m/%d/%Y").date()


def parse_fd_xml(xml: str) -> list[dict]:
    """Extract Periodic Transaction Reports (FilingType P) from the bulk FD XML."""
    def _f(rec: str, tag: str) -> str:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", rec, re.S)
        return m.group(1).strip() if m else ""

    out: list[dict] = []
    for rec in re.findall(r"<Member>(.*?)</Member>", xml, re.S):
        if "<FilingType>P</FilingType>" not in rec:
            continue
        out.append({
            "member": f"{_f(rec, 'First')} {_f(rec, 'Last')}".strip(),
            "filing_date": _f(rec, "FilingDate"),
            "doc_id": _f(rec, "DocID"),
            "year": _f(rec, "Year"),
        })
    return out


def parse_ptr_purchases(text: str) -> list[dict]:
    """Parse PURCHASE rows from a PTR PDF's text → [{ticker, transaction_date}].

    Each holding line looks like '... (AMZN) [ST] P 03/16/2026 03/16/2026 $1,001...'.
    We keep rows whose transaction type is a purchase (starts 'P'), skip sales 'S'.
    """
    purchases: list[dict] = []
    for line in text.splitlines():
        m = _TICKER_RE.search(line)
        if not m:
            continue
        after = line[m.end():].lstrip()
        # transaction type is the first token after the ticker bracket
        if not after[:1].upper() == "P":  # 'P' purchase; 'S' sale; 'E'/'R' other
            continue
        dates = _DATE_RE.findall(line)
        if not dates:
            continue
        purchases.append({"ticker": m.group(1), "transaction_date": dates[0]})
    return purchases


class CongressTradesSource:
    """House PTR purchases as point-in-time observations (free, no API key)."""

    def __init__(self, sleep=None):
        # sleep injectable for tests; real runs are gentle on the House server.
        import time
        self._sleep = sleep if sleep is not None else time.sleep

    def _get(self, url: str) -> bytes:
        return urllib.request.urlopen(
            urllib.request.Request(url, headers=_UA), timeout=45
        ).read()

    def fetch_recent_purchases(
        self, years: list[str], max_filings: int = 80
    ) -> list[CongressObservation]:
        out: list[CongressObservation] = []
        for yr in years:
            try:
                raw = self._get(_FD_ZIP.format(yr=yr))
                z = zipfile.ZipFile(io.BytesIO(raw))
                xml = z.read(next(n for n in z.namelist() if n.endswith(".xml"))).decode(
                    "utf-8", "ignore"
                )
            except Exception as exc:  # noqa: BLE001 - whole-year fetch failed; skip
                _LOG.warning("congress: %sFD.zip failed: %s", yr, exc)
                continue
            ptrs = parse_fd_xml(xml)
            for ptr in ptrs[-max_filings:]:  # most recent filings
                out.extend(self._observations_from_ptr(yr, ptr))
                self._sleep(0.3)
        return out

    def _observations_from_ptr(self, yr: str, ptr: dict) -> list[CongressObservation]:
        doc, filing = ptr["doc_id"], ptr["filing_date"]
        if not doc or not filing:
            return []
        url = _PTR_PDF.format(yr=ptr.get("year") or yr, doc=doc)
        try:
            known = _to_date(filing)
            text = "\n".join(
                p.extract_text() or "" for p in PdfReader(io.BytesIO(self._get(url))).pages
            )
        except Exception as exc:  # noqa: BLE001 - scanned/unparseable PTR; log + skip
            _LOG.warning("congress: skip PTR %s (%s)", doc, exc)
            return []
        obs: list[CongressObservation] = []
        for row in parse_ptr_purchases(text):
            try:
                tdate = _to_date(row["transaction_date"])
                if tdate > known:  # malformed; filing can't precede public date
                    tdate = known
                obs.append(CongressObservation(
                    member=ptr["member"], ticker=row["ticker"], transaction_date=tdate,
                    timestamp_known=known, amount="", url=url, doc_id=doc,
                ))
            except Exception:  # noqa: BLE001 - bad row; skip
                continue
        return obs
