"""edgartools-backed 13F source: follow famous investors by what they ACTUALLY
bought (SEC Form 13F-HR), not by what they tweet.

The honest, point-in-time version of "follow Burry/Buffett/Ackman": each quarter
a manager discloses holdings ~45 days after quarter end. We emit a signal only
for a NEW LONG SHARE position (in the latest 13F, not in the prior quarter), and
we IGNORE puts/calls — a put on PLTR is bearish, so "they hold PLTR" must never
become "buy PLTR". timestamp_known = filing date (the first an outsider sees it);
timestamp_event = report period (quarter end). The ~45-day lag is real and shown
honestly by the harness. The ONLY module besides edgar_form4 importing `edgar`.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

import pandas as pd
from edgar import Company, set_identity

_LOG = logging.getLogger(__name__)

# A starter roster of famous managers -> SEC CIK. Extend freely.
FAMOUS_FUNDS: dict[str, str] = {
    "Scion / Michael Burry": "0001649339",
    "Berkshire / Warren Buffett": "0001067983",
    "Pershing Square / Bill Ackman": "0001336528",
    "Appaloosa / David Tepper": "0001656456",
    "Bridgewater / Ray Dalio": "0001350694",
}


@dataclass(frozen=True)
class HoldingObservation:
    fund: str
    ticker: str
    issuer: str
    value: float
    shares: float
    put_call: str            # "" long shares, "Put"/"Call" options (we keep only "")
    timestamp_event: dt.date  # report period (quarter end)
    timestamp_known: dt.date  # filing date (point-in-time)
    url: str
    accession_no: str

    def __post_init__(self) -> None:
        if self.timestamp_known < self.timestamp_event:
            raise ValueError("timestamp_known (filing) must not predate event (report period)")


def _to_date(value: object) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _long_holdings(infotable: pd.DataFrame) -> dict[str, dict]:
    """Map ticker -> row dict for LONG SHARE positions only (blank PutCall)."""
    out: dict[str, dict] = {}
    if infotable is None or infotable.empty:
        return out
    for row in infotable.itertuples(index=False):
        put_call = str(getattr(row, "PutCall", "") or "").strip()
        ticker = str(getattr(row, "Ticker", "") or "").strip()
        if put_call or not ticker:
            continue  # skip options and rows without a usable ticker
        out[ticker] = {
            "issuer": str(getattr(row, "Issuer", "") or ""),
            "value": float(getattr(row, "Value", 0) or 0),
            "shares": float(str(getattr(row, "SharesPrnAmount", 0) or 0).replace(",", "")),
        }
    return out


class ThirteenFSource:
    """Fetch each fund's two most recent 13F-HR and emit NEW long positions."""

    def __init__(self, identity: str | None, funds: dict[str, str] | None = None):
        if not identity:
            raise ValueError("SEC identity required (set SEC_IDENTITY in .env)")
        self._identity = identity
        self._funds = funds if funds is not None else FAMOUS_FUNDS

    def fetch_new_long_positions(
        self, fund_names: list[str]
    ) -> list[HoldingObservation]:
        set_identity(self._identity)
        out: list[HoldingObservation] = []
        for name in fund_names:
            cik = self._funds.get(name)
            if not cik:
                _LOG.warning("unknown fund %s; skipping", name)
                continue
            try:
                out.extend(self._new_positions_for_fund(name, cik))
            except Exception as exc:  # log + skip, never abort the roster
                _LOG.warning("skip 13F for %s: %s", name, exc)
        return out

    def _new_positions_for_fund(self, name: str, cik: str) -> list[HoldingObservation]:
        filings = list(Company(cik).get_filings(form="13F-HR"))
        if not filings:
            return []
        latest = filings[0]
        latest_obj = latest.obj()
        latest_long = _long_holdings(latest_obj.infotable)
        prior_long: dict[str, dict] = {}
        if len(filings) > 1:
            prior_long = _long_holdings(filings[1].obj().infotable)
        known = _to_date(latest.filing_date)
        event = _to_date(latest_obj.report_period)
        url = str(getattr(latest, "homepage_url", "") or "")
        new_tickers = [t for t in latest_long if t not in prior_long]
        return [
            HoldingObservation(
                fund=name,
                ticker=ticker,
                issuer=latest_long[ticker]["issuer"],
                value=latest_long[ticker]["value"],
                shares=latest_long[ticker]["shares"],
                put_call="",
                timestamp_event=event,
                timestamp_known=known,
                url=url,
                accession_no=str(latest.accession_no),
            )
            for ticker in new_tickers
        ]
