import datetime as dt
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from signal_trader.sources.edgar_form4 import EdgarForm4Source


def _form4_obj(code="P", acq="A", has_plan=False):
    # Mirrors the real edgartools 5.36.0 Form4 shape: obj.issuer.ticker,
    # obj.insider_name, obj.position, obj.footnotes (no has_10b5_1_plan flag).
    obj = MagicMock()
    obj.footnotes = (
        {"F1": "Shares sold pursuant to a Rule 10b5-1 trading plan."}
        if has_plan
        else {}
    )
    obj.position = "Director"
    obj.insider_name = "Jane Doe"
    obj.issuer = MagicMock(ticker="AAPL")
    obj.market_trades = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-10")],
            "Shares": [1000.0],
            "Price": [150.0],
            "AcquiredDisposed": [acq],
            "Code": [code],
            "Remaining": [5000.0],
            "Security": ["Common Stock"],
        }
    )
    return obj


def _filing(obj, filing_date="2024-01-12", accession="0000000000-24-000001"):
    f = MagicMock()
    f.filing_date = filing_date
    f.accession_no = accession
    f.obj.return_value = obj
    return f


def _patched_company(filings):
    company = MagicMock()
    company.get_filings.return_value = filings
    return company


def test_fetch_maps_form4_rows_to_observations():
    filings = [_filing(_form4_obj())]
    with patch("signal_trader.sources.edgar_form4.set_identity") as si, patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company(filings),
    ):
        src = EdgarForm4Source(identity="Nico Sutheimer nico@example.com")
        out = src.fetch(["AAPL"], "2024-01-01", "2024-01-31")

    si.assert_called_once_with("Nico Sutheimer nico@example.com")
    assert len(out) == 1
    obs = out[0]
    assert obs.ticker == "AAPL"
    assert obs.transaction_code == "P"
    assert obs.acquired_disposed == "A"
    assert obs.shares == 1000.0
    assert obs.price == 150.0
    assert obs.timestamp_event == dt.date(2024, 1, 10)
    assert obs.timestamp_known == dt.date(2024, 1, 12)
    assert obs.is_10b5_1 is False
    assert obs.role == "Director"
    assert obs.accession_no == "0000000000-24-000001"


def test_fetch_passes_filing_date_range_to_get_filings():
    company = _patched_company([])
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company", return_value=company
    ):
        EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-06-30")
    _, kwargs = company.get_filings.call_args
    assert kwargs["form"] == "4"
    assert kwargs["filing_date"] == "2024-01-01:2024-06-30"


def test_multi_row_form4_yields_one_observation_per_trade():
    obj = _form4_obj()
    obj.market_trades = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-10"), pd.Timestamp("2024-01-10")],
            "Shares": [1000.0, 500.0],
            "Price": [150.0, 151.0],
            "AcquiredDisposed": ["A", "A"],
            "Code": ["P", "P"],
            "Remaining": [5000.0, 5500.0],
            "Security": ["Common Stock", "Common Stock"],
        }
    )
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company([_filing(obj)]),
    ):
        out = EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-01-31")
    assert len(out) == 2
    assert {o.shares for o in out} == {1000.0, 500.0}


def test_empty_identity_raises_before_network():
    with pytest.raises(ValueError):
        EdgarForm4Source(identity=None)


def test_unparseable_filing_is_skipped_not_silently_truncated(caplog):
    bad = _filing(_form4_obj())
    bad.obj.side_effect = RuntimeError("parse error")
    good = _filing(_form4_obj(), filing_date="2024-01-15", accession="acc-2")
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company([bad, good]),
    ):
        out = EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-01-31")
    assert len(out) == 1  # good one survives
    assert any("skip" in r.message.lower() for r in caplog.records)


# Fix 5: None/empty market_trades is a normal case, not a parse error
def test_none_market_trades_is_clean_skip_no_warning(caplog):
    """Filing with market_trades=None (no P/S rows) must not log a warning."""
    import logging
    obj = _form4_obj()
    obj.market_trades = None
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company([_filing(obj)]),
    ):
        with caplog.at_level(logging.WARNING, logger="signal_trader.sources.edgar_form4"):
            out = EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-01-31")
    assert out == []
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


def test_empty_market_trades_is_clean_skip_no_warning(caplog):
    """Filing with empty DataFrame market_trades must not log a warning."""
    import logging
    obj = _form4_obj()
    obj.market_trades = pd.DataFrame()
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company([_filing(obj)]),
    ):
        with caplog.at_level(logging.WARNING, logger="signal_trader.sources.edgar_form4"):
            out = EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-01-31")
    assert out == []
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)
