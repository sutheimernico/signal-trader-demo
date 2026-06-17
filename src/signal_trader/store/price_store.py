"""SQLite store for daily price bars (the structured cache).

One table, primary key (ticker, date) so re-fetches upsert cleanly.
`fetched_at` records when the row entered the cache (data-lag visibility).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_bars (
    ticker     TEXT    NOT NULL,
    date       TEXT    NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    source     TEXT    NOT NULL DEFAULT 'yfinance',
    fetched_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, date)
);
"""


class PriceBarStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def upsert_bars(self, bars: pd.DataFrame, source: str = "yfinance") -> None:
        if bars.empty:
            return
        rows = bars[_COLUMNS].copy()
        rows["date"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d")
        records = [
            (*tuple(r), source)
            for r in rows.itertuples(index=False, name=None)
        ]
        with self._connect() as con:
            con.executemany(
                "INSERT OR REPLACE INTO price_bars "
                "(ticker, date, open, high, low, close, volume, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                records,
            )

    def read_bars(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        placeholders = ",".join("?" for _ in tickers)
        query = (
            f"SELECT {', '.join(_COLUMNS)} FROM price_bars "
            f"WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ? "
            "ORDER BY ticker, date"
        )
        with self._connect() as con:
            out = pd.read_sql_query(query, con, params=[*tickers, start, end])
        out["date"] = pd.to_datetime(out["date"])
        return out

    def cached_tickers(self) -> set[str]:
        with self._connect() as con:
            rows = con.execute("SELECT DISTINCT ticker FROM price_bars").fetchall()
        return {r[0] for r in rows}
