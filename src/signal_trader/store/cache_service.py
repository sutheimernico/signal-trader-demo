"""Fetch-through-cache: pull once from the provider, serve from cache after.

Backtests read from this, never from the live provider — reproducible and
rate-limit-free (Spec §5.1). A ticker is 'cached' if its Parquet file exists.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from signal_trader.market_data.provider import PriceProvider
from signal_trader.store.bar_cache import BarCache
from signal_trader.store.price_store import PriceBarStore


class CacheService:
    def __init__(self, provider: PriceProvider, parquet_dir: Path, db_path: Path):
        self.provider = provider
        self.cache = BarCache(parquet_dir)
        self.store = PriceBarStore(db_path)

    def backfill(self, tickers: list[str], start: str, end: str) -> None:
        missing = [t for t in tickers if not self.cache.has(t)]
        if not missing:
            return
        bars = self.provider.fetch(missing, start, end)
        if bars.empty:
            return
        self.store.upsert_bars(bars)
        for ticker, group in bars.groupby("ticker"):
            self.cache.write(str(ticker), group.reset_index(drop=True))

    def load_close_matrix(
        self, tickers: list[str], start: str, end: str
    ) -> pd.DataFrame:
        bars = self.store.read_bars(tickers, start, end)
        wide = bars.pivot(index="date", columns="ticker", values="close")
        wide.index.name = "date"
        return wide[[t for t in tickers if t in wide.columns]]
