import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def trending_close():
    """Deterministic upward-trending daily close with mild noise (300 bars)."""
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    rng = np.random.default_rng(42)
    drift = np.linspace(0, 0.6, len(idx))
    noise = rng.normal(0, 0.01, len(idx)).cumsum()
    close = 100 * np.exp(drift + noise)
    return pd.Series(close, index=idx, name="Close")


@pytest.fixture
def ohlcv_frame(trending_close):
    """Capitalized OHLCV frame for backtesting.py from a close series."""
    close = trending_close
    return pd.DataFrame(
        {
            "Open": close.shift(1).fillna(close.iloc[0]),
            "High": close * 1.005,
            "Low": close * 0.995,
            "Close": close,
            "Volume": 1_000_000.0,
        }
    )
