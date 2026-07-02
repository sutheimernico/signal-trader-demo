import datetime as dt
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import scripts.run_ml_experiment as ml

from signal_trader.paper.broker import Fill
from signal_trader.strategy.shortterm.survivorship import DelistingEvent


class FakeBroker:
    def __init__(self, *a, **k):
        pass
    def submit_market_buy(self, symbol, qty):
        return Fill(order_id="o", symbol=symbol, qty=qty, price=100.0,
                    filled_at=dt.datetime(2024, 1, 2, 15, tzinfo=dt.UTC),
                    side="buy")


def _universe(tickers, start, end):
    idx = pd.date_range("2023-01-01", periods=120, freq="B")
    rng = np.random.default_rng(7)
    return {t: pd.Series(100 * (1 + rng.normal(0.0004, 0.02, 120)).cumprod(), index=idx)
            for t in ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]}


def test_experiment_prints_honest_scorecard_no_trade(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    monkeypatch.setattr(ml.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
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


def test_consensus_flag_loads_signals_and_labels_scorecard(tmp_path, monkeypatch, capsys):
    """--consensus opts the point-in-time consensus feature into the SAME OOS A/B
    and labels the scorecard so the run is self-documenting."""
    from signal_trader.strategy.shortterm.consensus import ConsensusSignal

    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    called = {}

    def fake_load_consensus(tickers, start, end, **kwargs):
        called["yes"] = True
        return [ConsensusSignal(ticker="AAA", timestamp_known=dt.date(2023, 2, 1),
                                source="insider_form4", actor_id="x")]

    monkeypatch.setattr(ml, "_load_consensus_signals", fake_load_consensus)
    monkeypatch.setattr(ml.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
    with patch.object(sys, "argv",
                      ["run_ml_experiment.py", "--tickers", "AAA", "BBB",
                       "--start", "2023-01-01", "--end", "2024-12-31",
                       "--horizon", "3", "--n-splits", "2", "--test-size", "10",
                       "--top-k", "2", "--no-trade", "--consensus"]):
        ml.main()
    out = capsys.readouterr().out
    assert called.get("yes"), "expected --consensus to load consensus signals"
    assert "consensus" in out.lower()


def test_load_consensus_signals_includes_backward_window_before_start(tmp_path, monkeypatch):
    """The backward window needs signals known BEFORE --start to populate early
    bars; the loader must widen its read by window_days, else early-bar counts
    are silently understated (conservative, but it weakens the honest A/B)."""
    from signal_trader.store.signal_store import SignalRecord, SignalStore

    db = tmp_path / "sig.sqlite"
    store = SignalStore(db)
    store.insert_signals([
        SignalRecord(
            ticker="AAA", source="insider_form4", signal_type="buy", direction="long",
            timestamp_event=dt.date(2023, 12, 20), timestamp_known=dt.date(2023, 12, 28),
            price_at_known=10.0, raw_payload={"accession_no": "pre"}, confidence=0.5,
        ),  # known 4 days BEFORE start=2024-01-01, inside a 30d window
    ])
    monkeypatch.setattr(ml.config, "SQLITE_PATH", db)
    got = ml._load_consensus_signals(["AAA"], "2024-01-01", "2024-12-31", window_days=30)
    assert any(s.actor_id == "pre" for s in got), "pre-start signal must be loaded"


def test_no_consensus_flag_does_not_load_signals(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    called = {"yes": False}
    monkeypatch.setattr(ml, "_load_consensus_signals",
                        lambda *a, **k: called.__setitem__("yes", True) or [])
    monkeypatch.setattr(ml.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
    with patch.object(sys, "argv",
                      ["run_ml_experiment.py", "--tickers", "AAA", "BBB",
                       "--start", "2023-01-01", "--end", "2024-12-31",
                       "--horizon", "3", "--n-splits", "2", "--test-size", "10",
                       "--top-k", "2", "--no-trade"]):
        ml.main()
    assert called["yes"] is False  # default OFF: never touches the signal store


def test_survivorship_stress_flag_labels_scorecard(tmp_path, monkeypatch, capsys):
    """--survivorship-stress loads the cached delisting list and prints the FREE
    synthetic-delisting block with its honest partial-correction caveat."""
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    monkeypatch.setattr(
        ml, "_load_delisting_events",
        lambda tickers: [DelistingEvent(ticker="AAA", delisted_known=dt.date(2023, 6, 1))],
    )
    monkeypatch.setattr(ml.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
    with patch.object(sys, "argv",
                      ["run_ml_experiment.py", "--tickers", "AAA", "BBB",
                       "--start", "2023-01-01", "--end", "2024-12-31",
                       "--horizon", "3", "--n-splits", "2", "--test-size", "10",
                       "--top-k", "2", "--no-trade",
                       "--survivorship-stress", "--delisting-haircut", "-0.6"]):
        ml.main()
    out = capsys.readouterr().out
    assert "survivorship stress" in out.lower()
    assert "1 universe name" in out  # AAA matched
    assert "needs nico" in out.lower() or "crsp" in out.lower()


def test_no_survivorship_flag_does_not_load_delistings(tmp_path, monkeypatch):
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    called = {"yes": False}
    monkeypatch.setattr(ml, "_load_delisting_events",
                        lambda *a, **k: called.__setitem__("yes", True) or [])
    monkeypatch.setattr(ml.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
    with patch.object(sys, "argv",
                      ["run_ml_experiment.py", "--tickers", "AAA", "BBB",
                       "--start", "2023-01-01", "--end", "2024-12-31",
                       "--horizon", "3", "--n-splits", "2", "--test-size", "10",
                       "--top-k", "2", "--no-trade"]):
        ml.main()
    assert called["yes"] is False  # default OFF


def test_experiment_logs_trial_and_reports_growing_trial_count(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    trial_log = tmp_path / "trial_log.jsonl"
    monkeypatch.setattr(ml.config, "TRIAL_LOG_PATH", trial_log)
    argv = ["run_ml_experiment.py", "--tickers", "AAA", "BBB",
            "--start", "2023-01-01", "--end", "2024-12-31",
            "--horizon", "3", "--n-splits", "2", "--test-size", "10",
            "--top-k", "2", "--no-trade"]

    with patch.object(sys, "argv", argv):
        ml.main()
    first_out = capsys.readouterr().out
    assert "1 trial(s) logged" in first_out
    assert "deflated-Sharpe" in first_out

    with patch.object(sys, "argv", argv):
        ml.main()
    second_out = capsys.readouterr().out
    assert "2 trial(s) logged" in second_out


def test_experiment_opens_autonomous_paper_trades(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ml, "_load_close_lookup", _universe)
    monkeypatch.setattr(ml, "AlpacaPaperBroker", FakeBroker)
    monkeypatch.setattr(ml.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(ml.config, "alpaca_credentials", lambda: ("k", "s"))
    monkeypatch.setattr(ml.config, "TRIAL_LOG_PATH", tmp_path / "trial_log.jsonl")
    with patch.object(sys, "argv",
                      ["run_ml_experiment.py", "--tickers", "AAA",
                       "--start", "2023-01-01", "--end", "2024-12-31",
                       "--horizon", "3", "--n-splits", "2", "--test-size", "10",
                       "--top-k", "2"]):
        ml.main()
    out = capsys.readouterr().out
    assert "autonomous ML paper trade" in out
