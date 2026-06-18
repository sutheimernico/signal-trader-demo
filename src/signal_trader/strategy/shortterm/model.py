"""Forecaster seam for the ML experiment (Phase 4).

A vendor-neutral interface so the evaluation/paper loop never depends on
lightgbm directly and can be faked in tests. GBDTForecaster is a gradient-boosted
regression on the point-in-time forward-return label (Spec: GBDT default, no LLM
price prediction). It predicts an expected forward return per row; the strategy
goes long the top-ranked names. Models are FIT PER FOLD on training data only —
never on the full series (that would leak the future backward).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd


@runtime_checkable
class Forecaster(Protocol):
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None: ...
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...


class GBDTForecaster:
    """LightGBM gradient-boosted regressor on the forward-return label."""

    def __init__(self, n_estimators: int = 200, random_state: int = 0, **params):
        # Imported here so the seam stays importable even if lightgbm is absent
        # in a minimal env; the evaluation path requires it, tests fake it.
        from lightgbm import LGBMRegressor

        self._model = LGBMRegressor(
            n_estimators=n_estimators,
            random_state=random_state,
            verbosity=-1,
            **params,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        self._model.fit(X, y)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self._model.predict(X), dtype=float)
