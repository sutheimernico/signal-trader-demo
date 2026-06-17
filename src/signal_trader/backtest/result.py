"""Common result shape so both engines return the same thing.

`equity_curve` is the post-cost account value indexed by date; downstream
metrics derive returns from it. This is the seam that lets the report diff
event-driven vs vectorized on equal footing.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class BacktestResult:
    engine: str
    equity_curve: pd.Series
    n_trades: int

    def returns(self) -> pd.Series:
        """Periodic returns derived from the equity curve."""
        return self.equity_curve.pct_change().dropna()
