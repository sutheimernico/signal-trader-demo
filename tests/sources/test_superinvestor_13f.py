import datetime as dt
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from signal_trader.sources.superinvestor_13f import (
    HoldingObservation,
    ThirteenFSource,
)


def _infotable(rows):
    return pd.DataFrame(rows)


def _thirteenf(infotable, report_period, filing_date, accession):
    obj = MagicMock()
    obj.infotable = infotable
    obj.report_period = report_period
    f = MagicMock()
    f.filing_date = filing_date
    f.accession_no = accession
    f.homepage_url = f"https://sec.gov/{accession}"
    f.obj.return_value = obj
    return f


def _company(filings):
    c = MagicMock()
    c.get_filings.return_value = filings
    return c


# Q2: holds AAPL. Q3 (latest): adds MSFT (new long), keeps AAPL, adds PLTR PUT (bearish).
_PRIOR = _thirteenf(
    _infotable([
        {"Issuer": "APPLE INC", "Ticker": "AAPL", "Cusip": "037833100",
         "Value": 1000, "PutCall": "", "SharesPrnAmount": 10},
    ]),
    "2025-06-30", "2025-08-10", "acc-q2",
)
_LATEST = _thirteenf(
    _infotable([
        {"Issuer": "APPLE INC", "Ticker": "AAPL", "Cusip": "037833100",
         "Value": 1000, "PutCall": "", "SharesPrnAmount": 10},
        {"Issuer": "MICROSOFT CORP", "Ticker": "MSFT", "Cusip": "594918104",
         "Value": 2000, "PutCall": "", "SharesPrnAmount": 20},
        {"Issuer": "PALANTIR", "Ticker": "PLTR", "Cusip": "69608A108",
         "Value": 9000, "PutCall": "Put", "SharesPrnAmount": 50},
    ]),
    "2025-09-30", "2025-11-03", "acc-q3",
)


def test_emits_only_new_long_positions_not_puts_not_existing():
    with patch("signal_trader.sources.superinvestor_13f.set_identity"), patch(
        "signal_trader.sources.superinvestor_13f.Company",
        return_value=_company([_LATEST, _PRIOR]),
    ):
        src = ThirteenFSource(identity="X y@z.com", funds={"Burry": "0001649339"})
        out = src.fetch_new_long_positions(["Burry"])
    tickers = {o.ticker for o in out}
    assert tickers == {"MSFT"}          # MSFT is the new long; AAPL not new; PLTR is a put
    o = next(iter(out))
    assert o.fund == "Burry"
    assert o.put_call == ""
    assert o.timestamp_event == dt.date(2025, 9, 30)   # report period
    assert o.timestamp_known == dt.date(2025, 11, 3)   # filing date (PIT)
    assert isinstance(o, HoldingObservation)


def test_known_not_before_event():
    with pytest.raises(ValueError):
        HoldingObservation(
            fund="F", ticker="X", issuer="X", value=1.0, shares=1.0, put_call="",
            timestamp_event=dt.date(2025, 9, 30), timestamp_known=dt.date(2025, 6, 1),
            url="u", accession_no="a",
        )


def test_empty_identity_raises():
    with pytest.raises(ValueError):
        ThirteenFSource(identity=None, funds={"Burry": "1"})
