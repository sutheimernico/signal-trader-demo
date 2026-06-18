"""Per-source hit-rate, avg forward return, and DATA LAG (Acceptance §3, §4).

Hit-rate and avg forward return are computed only over signals with enough
forward bars in the cache — a signal we cannot score is EXCLUDED, never counted
as a miss (that would manufacture pessimism the same way silent truncation
manufactures optimism). Data lag = mean(timestamp_known - timestamp_event) in
days, making each source's reporting delay explicit in the system.
"""
from __future__ import annotations

import pandas as pd

from signal_trader.signals.scoring.forward_return import forward_return
from signal_trader.store.signal_store import SignalStore, SourceScoreRecord


def score_source(
    store: SignalStore,
    source: str,
    close_lookup: dict[str, pd.Series],
    horizon: int = 5,
    window_label: str = "5d",
    persist: bool = False,
    start: str | None = None,
    end: str | None = None,
) -> SourceScoreRecord:
    """Compute (and optionally persist) the SourceScore for one source.

    `start`/`end` (timestamp_known window) must match the window the P&L is
    reported over, so hit-rate and lag describe the same signal population.
    """
    signals = store.read_signals(source=source, start=start, end=end)
    returns: list[float] = []
    lags: list[int] = []
    for sig in signals:
        lags.append((sig.timestamp_known - sig.timestamp_event).days)
        close = close_lookup.get(sig.ticker)
        if close is None:
            continue
        fr = forward_return(close, sig.timestamp_known, horizon=horizon)
        if fr is not None:
            returns.append(fr)
    n = len(returns)
    hit_rate = sum(1 for r in returns if r > 0) / n if n else 0.0
    avg_ret = sum(returns) / n if n else 0.0
    avg_lag = sum(lags) / len(lags) if lags else 0.0
    record = SourceScoreRecord(
        source=source, window=window_label, n_signals=n,
        hit_rate=hit_rate, avg_forward_return=avg_ret, avg_data_lag_days=avg_lag,
    )
    if persist:
        store.upsert_source_score(record)
    return record
