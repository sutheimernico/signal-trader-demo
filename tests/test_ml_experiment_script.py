import datetime as dt
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd

import scripts.run_ml_experiment as ml
from signal_trader.paper.broker import Fill


class FakeBroker:
    def __init__(self, *a, **k):
        pass
    def submit_market_buy(self, symbol, qty):
        return Fill(order_id="o", symbol=symbol, qty=qty, price=100.0,
                    filled_at=dt.datetime(2024, 1, 2, 15, tzinfo=dt.timezone.utc),
                    side="buy")


def _universe(tickers, start, end):
    idx = pd.date_range("2023-01-01", periods=120, freq="B")
    rng = np.random.default_rng(7)
    return {t: pd.Series(100 * (1 + rng.normal(0.0004, 0.02, 120)).cumprod(), index=idx)
            for t in ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]}


def test_experiment_prints_honest_scorecard_no_trade(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    with patch.object(sys, "argv",
                      ["run_ml_experiment.py", "--tickers", "AAA", "BBB",
                       "--start", "2023-01-01", "--end", "2024-12-31",
                       "--horizon", "3", "--n-splits", "2", "--test-size", "10",
                       "--top-k", "2", "--no-trade"]):
        ml.main()
    out = capsys.readouterr().out
    assert "ML experiment" in out
    assert "baseline" in out.lower()
    assert ("BEAT" in out) or ("did NOT beat" in out)


def test_experiment_opens_autonomous_paper_trades(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    monkeypatch.setattr(ml, "AlpacaPaperBroker", FakeBroker)
    monkeypatch.setattr(ml.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(ml.config, "alpaca_credentials", lambda: ("k", "s"))
    with patch.object(sys, "argv",
                      ["run_ml_experiment.py", "--tickers", "AAA",
                       "--start", "2023-01-01", "--end", "2024-12-31",
                       "--horizon", "3", "--n-splits", "2", "--test-size", "10",
                       "--top-k", "2"]):
        ml.main()
    out = capsys.readouterr().out
    assert "autonomous ML paper trade" in out
