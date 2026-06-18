import datetime as dt

import pytest

from signal_trader.sources.congress_trades import (
    CongressObservation,
    parse_fd_xml,
    parse_ptr_purchases,
)

_XML = """
<FinancialDisclosure>
<Member><Last>Alford</Last><First>Mark</First><FilingType>P</FilingType>
<Year>2026</Year><FilingDate>3/31/2026</FilingDate><DocID>20034201</DocID></Member>
<Member><Last>Smith</Last><First>Jane</First><FilingType>O</FilingType>
<Year>2026</Year><FilingDate>2/01/2026</FilingDate><DocID>999</DocID></Member>
</FinancialDisclosure>
"""

_PTR_TEXT = """
Name: Hon. Mark Alford
NVIDIA Corporation - Common Stock (NVDA) [ST] P 03/16/2026 03/20/2026 $1,001 - $15,000
Amazon.com, Inc. - Common Stock (AMZN) [ST] S (partial) 03/16/2026 03/20/2026 $1,001 - $15,000
Apple Inc. - Common Stock (AAPL) [ST] P 03/10/2026 03/20/2026 $15,001 - $50,000
"""


def test_parse_fd_xml_keeps_only_ptr_filings():
    recs = parse_fd_xml(_XML)
    assert len(recs) == 1
    assert recs[0]["member"] == "Mark Alford"
    assert recs[0]["filing_date"] == "3/31/2026"
    assert recs[0]["doc_id"] == "20034201"


def test_parse_ptr_keeps_purchases_drops_sales():
    rows = parse_ptr_purchases(_PTR_TEXT)
    tickers = {r["ticker"] for r in rows}
    assert tickers == {"NVDA", "AAPL"}      # AMZN is a Sale -> dropped
    assert all(r["transaction_date"] for r in rows)


def test_observation_rejects_filing_before_transaction():
    with pytest.raises(ValueError):
        CongressObservation(
            member="X", ticker="NVDA", transaction_date=dt.date(2026, 3, 20),
            timestamp_known=dt.date(2026, 3, 10), amount="", url="u", doc_id="1",
        )
