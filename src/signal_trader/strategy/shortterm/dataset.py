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

from signal_trader.strategy.shortterm.consensus import (
    ConsensusSignal,
    consensus_buyers_known_le_t,
)


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
    # NOTE: calendar/seasonality features were tested (2026-06-18) and made OOS
    # WORSE (0.00505 -> 0.00297, lost to baseline) — overfitting. Kept off. The
    # helper stays for documented experiments behind an explicit opt-in only.
    # Label: enter next bar (t+1), exit `horizon` bars later. Strictly future.
    entry = close.shift(-1)
    exit_ = close.shift(-(1 + horizon))
    frame["__label__"] = exit_ / entry - 1.0
    return frame.dropna()


def _add_calendar(frame: pd.DataFrame) -> None:
    """Add point-in-time calendar/seasonality features from the date index alone.

    Derived only from the bar's own date — trivially leakage-free and identical
    in training and live prediction. Captures the seasonality Nico asked for
    (quarter, turn-of-month, weekday). Tree models split on these as regime cues.
    """
    idx = pd.DatetimeIndex(frame.index)
    frame["cal_dow"] = idx.dayofweek.astype(float)        # 0=Mon..4=Fri
    frame["cal_month"] = idx.month.astype(float)
    frame["cal_dom"] = idx.day.astype(float)
    frame["cal_turn_of_month"] = ((idx.day >= 26) | (idx.day <= 3)).astype(float)
    frame["cal_quarter_end_month"] = idx.month.isin([3, 6, 9, 12]).astype(float)


def _feature_frame(close: pd.Series, feature_windows: list[int]) -> pd.DataFrame:
    """Features only (no label) — for live prediction at 'today', point-in-time."""
    rets = close.pct_change(fill_method=None)
    cols: dict[str, pd.Series] = {}
    for w in feature_windows:
        cols[f"ret_{w}"] = close.pct_change(w, fill_method=None)
        cols[f"vol_{w}"] = rets.rolling(w).std()
    frame = pd.DataFrame(cols)
    # NOTE: calendar/seasonality features were tested (2026-06-18) and made OOS
    # WORSE (0.00505 -> 0.00297, lost to baseline) — overfitting. Kept off. The
    # helper stays for documented experiments behind an explicit opt-in only.
    return frame.dropna()


def latest_features(
    close_by_ticker: dict[str, pd.Series],
    feature_windows: list[int] | None = None,
) -> pd.DataFrame:
    """Most-recent point-in-time feature row per ticker (no forward label needed).

    Used by the autonomous paper loop to decide what to buy 'today': each ticker
    contributes the features of its latest fully-formed bar. Index (ticker, date).
    """
    windows = feature_windows if feature_windows is not None else [5, 10, 20]
    frames: list[pd.DataFrame] = []
    for ticker, close in close_by_ticker.items():
        frame = _feature_frame(close, windows)
        if frame.empty:
            continue
        last = frame.iloc[[-1]]
        last.index = pd.MultiIndex.from_product(
            [[ticker], last.index], names=["ticker", "date"]
        )
        frames.append(last)
    return pd.concat(frames) if frames else pd.DataFrame()


def build_dataset(
    close_by_ticker: dict[str, pd.Series],
    horizon: int = 5,
    feature_windows: list[int] | None = None,
    consensus_signals: list[ConsensusSignal] | None = None,
    consensus_window_days: int = 30,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build a point-in-time (X, y) dataset indexed by (ticker, date).

    ``consensus_signals`` is an explicit opt-in (default None = OFF), exactly the
    ``_add_calendar`` pattern: pass insider/congress/fund buy signals and a
    backward-window count of distinct point-in-time buyers is appended as
    ``consensus_buyers_known_le_t``. The join is strictly ``timestamp_known <= t``
    over the ALREADY-built (dropna'd) price rows, so a bar with no qualifying
    signal gets an explicit 0 — no fabricated row, no dropped row.
    """
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
    if consensus_signals is not None:
        full["consensus_buyers_known_le_t"] = consensus_buyers_known_le_t(
            full.index, consensus_signals, window_days=consensus_window_days
        )
    return full, y
