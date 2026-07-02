import sys
from unittest.mock import patch

import pandas as pd
import scripts.backfill as backfill  # noqa: E402
import scripts.generate_tearsheet as generate_tearsheet  # noqa: E402
import scripts.run_backtest as run_backtest  # noqa: E402


class FakeProvider:
    def fetch(self, tickers, start, end):
        frames = []
        for t in tickers:
            idx = pd.date_range("2018-01-01", periods=400, freq="B")
            frames.append(pd.DataFrame({
                "ticker": t, "date": idx,
                "open": 100.0, "high": 101.0, "low": 99.0,
                "close": (100 + (idx - idx[0]).days * 0.05),
                "volume": 1e6,
            }))
        return pd.concat(frames, ignore_index=True)


def test_backfill_main_runs_with_faked_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "YFinanceProvider", FakeProvider)
    monkeypatch.setattr(backfill.config, "PARQUET_DIR", tmp_path / "bars")
    monkeypatch.setattr(backfill.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    with patch.object(sys, "argv", ["backfill.py", "--tickers", "AAPL", "MSFT"]):
        backfill.main()
    assert (tmp_path / "bars" / "AAPL.parquet").exists()


def test_run_backtest_main_prints_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_backtest, "YFinanceProvider", FakeProvider)
    monkeypatch.setattr(run_backtest.config, "PARQUET_DIR", tmp_path / "bars")
    monkeypatch.setattr(run_backtest.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(run_backtest.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
    with patch.object(
        sys, "argv",
        ["run_backtest.py", "--ticker", "AAPL", "--lookback", "50"],
    ):
        run_backtest.main()
    out = capsys.readouterr().out
    assert "Foundation Report" in out
    assert "vectorbt" in out and "backtesting.py" in out


def test_run_backtest_logs_trial_and_reports_growing_trial_count(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_backtest, "YFinanceProvider", FakeProvider)
    monkeypatch.setattr(run_backtest.config, "PARQUET_DIR", tmp_path / "bars")
    monkeypatch.setattr(run_backtest.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    trial_log = tmp_path / "trial_log.jsonl"
    monkeypatch.setattr(run_backtest.config, "TRIAL_LOG_PATH", trial_log)
    argv = ["run_backtest.py", "--ticker", "AAPL", "--lookback", "50"]

    with patch.object(sys, "argv", argv):
        run_backtest.main()
    first_out = capsys.readouterr().out
    # A single trial has no dispersion evidence yet: DSR == plain PSR, but the
    # mechanism is already on and says so honestly.
    assert "DSR" in first_out
    assert "1 trial(s) logged" in first_out

    with patch.object(sys, "argv", argv):
        run_backtest.main()
    second_out = capsys.readouterr().out
    assert "2 trial(s) logged" in second_out


def test_generate_tearsheet_main_writes_html_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(generate_tearsheet, "YFinanceProvider", FakeProvider)
    monkeypatch.setattr(generate_tearsheet.config, "PARQUET_DIR", tmp_path / "bars")
    monkeypatch.setattr(generate_tearsheet.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(generate_tearsheet.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
    output_path = tmp_path / "out" / "aapl_tearsheet.html"
    with patch.object(
        sys, "argv",
        ["generate_tearsheet.py", "--ticker", "AAPL", "--lookback", "50",
         "--start", "2018-01-01", "--end", "2019-12-31", "--output", str(output_path)],
    ):
        generate_tearsheet.main()
    out = capsys.readouterr().out
    assert "Wrote tearsheet" in out
    assert output_path.exists()

    html = output_path.read_text(encoding="utf-8")
    assert "data:image/png;base64," in html
    assert "does NOT robustly beat the momentum baseline" in html  # honest note present
    assert "http://" not in html and "https://" not in html
