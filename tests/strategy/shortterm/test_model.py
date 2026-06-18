import numpy as np
import pandas as pd

from signal_trader.strategy.shortterm.model import Forecaster, GBDTForecaster


def test_protocol_is_runtime_checkable():
    class Dummy:
        def fit(self, X, y): ...
        def predict(self, X): return np.zeros(len(X))
    assert isinstance(Dummy(), Forecaster)


def test_gbdt_fits_and_predicts_one_score_per_row():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(60, 3)), columns=["a", "b", "c"])
    y = pd.Series(X["a"] * 0.5 + rng.normal(scale=0.1, size=60))
    model = GBDTForecaster(n_estimators=20, random_state=0)
    model.fit(X, y)
    preds = model.predict(X.iloc[:10])
    assert len(preds) == 10
    assert np.isfinite(preds).all()
