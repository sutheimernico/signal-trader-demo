import datetime as dt
import sys
from unittest.mock import patch

import pandas as pd
import scripts.ingest_insider as ingest
import scripts.run_insider_report as report

from signal_trader.sources.insider_source import InsiderObservation


class FakeSource:
    def __init__(self, *a, **k):
        pass

    def fetch(self, tickers, start, end):
        out = []
        for owner, day in [("A", 3), ("B", 4), ("C", 5)]:
            out.append(InsiderObservation(
                ticker="AAPL", reporting_owner=owner, role="Director",
                transaction_code="P", acquired_disposed="A", shares=100.0, price=10.0,
                timestamp_event=dt.date(2024, 1, day),
                timestamp_known=dt.date(2024, 1, day + 1),
                is_10b5_1=False, accession_no=f"{owner}-{day}",
            ))
        return out


def _fake_close_lookup(tickers, start, end):
    idx = pd.date_range("2024-01-01", periods=120, freq="B")
    return {"AAPL": pd.Series([100.0 + i for i in range(120)], index=idx)}


def test_ingest_then_report_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ingest, "EdgarForm4Source", FakeSource)
    monkeypatch.setattr(ingest.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(ingest, "_load_close_lookup", _fake_close_lookup)
    monkeypatch.setattr(ingest.config, "sec_identity", lambda: "X y@z.com")
    with patch.object(sys, "argv",
                      ["ingest_insider.py", "--tickers", "AAPL",
                       "--start", "2024-01-01", "--end", "2024-01-31"]):
        ingest.main()

    monkeypatch.setattr(report.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(report, "_load_close_lookup", _fake_close_lookup)
    with patch.object(sys, "argv",
                      ["run_insider_report.py", "--tickers", "AAPL",
                       "--start", "2024-01-01", "--end", "2024-06-30"]):
        report.main()
    out = capsys.readouterr().out
    assert "Insider Report" in out
    assert "vectorbt" in out and "backtesting.py" in out
    assert "Buy & Hold (after costs)" in out
    assert "hit_rate" in out and "data_lag" in out


def test_sec_smoke_importable_without_network():
    import scripts.sec_smoke as smoke  # noqa: F401
