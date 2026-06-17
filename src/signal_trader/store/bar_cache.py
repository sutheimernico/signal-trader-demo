"""Per-ticker Parquet cache for raw bars (the columnar cache).

One file per ticker keeps re-fetches cheap and the working set small.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


class BarCache:
    def __init__(self, parquet_dir: Path):
        self.parquet_dir = Path(parquet_dir)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, ticker: str) -> Path:
        return self.parquet_dir / f"{ticker}.parquet"

    def has(self, ticker: str) -> bool:
        return self._path(ticker).exists()

    def write(self, ticker: str, bars: pd.DataFrame) -> None:
        bars.to_parquet(self._path(ticker), index=False)

    def read(self, ticker: str) -> pd.DataFrame:
        return pd.read_parquet(self._path(ticker))
