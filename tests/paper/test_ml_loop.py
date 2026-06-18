import datetime as dt

import numpy as np
import pandas as pd

from signal_trader.paper.broker import Fill
from signal_trader.paper.ml_loop import open_ml_positions
from signal_trader.store.paper_trade_store import PaperTradeStore
from signal_trader.strategy.shortterm.dataset import latest_features


class FakeBroker:
    def __init__(self):
        self.calls = []
    def submit_market_buy(self, symbol, qty):
        self.calls.append(symbol)
        return Fill(order_id=f"o{len(self.calls)}", symbol=symbol, qty=qty,
                    price=100.0, filled_at=dt.datetime(2024, 1, 2, 15, tzinfo=dt.UTC),
                    side="buy")


class RankBy:
    """Predicts a fixed score per ticker so the top-k is deterministic."""
    def __init__(self, scores):
        self._scores = scores
    def fit(self, X, y): ...
    def predict(self, X):
        return np.array([self._scores[t] for (t, _) in X.index], dtype=float)


def _universe():
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    out = {}
    for i, t in enumerate(["AAA", "BBB", "CCC", "DDD"]):
        out[t] = pd.Series(100 + np.arange(30) * (i + 1), index=idx, dtype=float)
    return out


def test_opens_top_k_predicted_names(tmp_path):
    X = latest_features(_universe(), feature_windows=[5])
    store = PaperTradeStore(tmp_path / "t.sqlite")
    broker = FakeBroker()
    model = RankBy({"AAA": 0.1, "BBB": 0.9, "CCC": 0.5, "DDD": 0.2})
    n = open_ml_positions(X, model, store, broker, top_k=2, qty=3.0)
    assert n == 2
    assert set(broker.calls) == {"BBB", "CCC"}  # the two highest scores


def test_idempotent_no_double_open(tmp_path):
    X = latest_features(_universe(), feature_windows=[5])
    store = PaperTradeStore(tmp_path / "t.sqlite")
    broker = FakeBroker()
    model = RankBy({"AAA": 0.1, "BBB": 0.9, "CCC": 0.5, "DDD": 0.2})
    open_ml_positions(X, model, store, broker, top_k=2)
    n2 = open_ml_positions(X, model, store, broker, top_k=2)
    assert n2 == 0
    assert len(store.read_trades()) == 2
