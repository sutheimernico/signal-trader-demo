"""Leakage-safe feature/label dataset for the ML experiment (Phase 4).

Point-in-time is the whole game here. For each (ticker, date t):
  - FEATURES use only data AT OR BEFORE t (multi-window returns + rolling
    volatility). Nothing from the future enters a feature.
  - LABEL is the forward return of a trade ENTERED ON THE NEXT BAR (t+1) and
    held `horizon` bars: close[t+1+horizon] / close[t+1] - 1. The decision at t
    can only act on t+1 (the Phase-1 PIT rule), so features and label never
    overlap.
Rows lacking a full feature window or a full forward label window are DROPPED,
never zero-filled — a fabricated row is silent leakage/pessimism.
"""
from __future__ import annotations

import pandas as pd


def _ticker_frame(
    close: pd.Series, horizon: int, feature_windows: list[int]
) -> pd.DataFrame:
    # fill_method=None: a missing bar must propagate to NaN (then dropped), never
    # be forward-filled into a fabricated 0% return / understated volatility.
    rets = close.pct_change(fill_method=None)
    cols: dict[str, pd.Series] = {}
    for w in feature_windows:
        cols[f"ret_{w}"] = close.pct_change(w, fill_method=None)  # close[t]/close[t-w]-1, uses <= t
        cols[f"vol_{w}"] = rets.rolling(w).std()      # vol of returns up to t
    frame = pd.DataFrame(cols)
    # Label: enter next bar (t+1), exit `horizon` bars later. Strictly future.
    entry = close.shift(-1)
    exit_ = close.shift(-(1 + horizon))
    frame["__label__"] = exit_ / entry - 1.0
    return frame.dropna()


def build_dataset(
    close_by_ticker: dict[str, pd.Series],
    horizon: int = 5,
    feature_windows: list[int] | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build a point-in-time (X, y) dataset indexed by (ticker, date)."""
    windows = feature_windows if feature_windows is not None else [5, 10, 20]
    frames: list[pd.DataFrame] = []
    for ticker, close in close_by_ticker.items():
        frame = _ticker_frame(close, horizon, windows)
        frame.index = pd.MultiIndex.from_product(
            [[ticker], frame.index], names=["ticker", "date"]
        )
        frames.append(frame)
    if not frames:
        return pd.DataFrame(), pd.Series(dtype=float)
    full = pd.concat(frames)
    y = full.pop("__label__")
    return full, y
