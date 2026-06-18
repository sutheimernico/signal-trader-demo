"""SQLite persistence for PaperTrade (Spec §9).

Records the paper-only lifecycle of an accepted suggestion: entry on open,
exit + realized pnl on close. Fills/costs are logged as they actually happen
(Spec §8.1) — the forward-paper run is plumbing validation, never a performance
claim (Spec §3, §8.10). An open trade has null exit_price/exit_time/pnl. The
row id is an autoincrement surrogate so a ticker can have many trades over time.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker               TEXT NOT NULL,
    side                 TEXT NOT NULL,
    qty                  REAL NOT NULL,
    entry_price          REAL NOT NULL,
    entry_time           TEXT NOT NULL,
    exit_price           REAL,
    exit_time            TEXT,
    pnl                  REAL,
    source_suggestion_id TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class PaperTradeRecord:
    ticker: str
    side: str
    qty: float
    entry_price: float
    entry_time: dt.datetime
    exit_price: float | None
    exit_time: dt.datetime | None
    pnl: float | None
    source_suggestion_id: str


@dataclass(frozen=True)
class StoredPaperTrade:
    id: int
    ticker: str
    side: str
    qty: float
    entry_price: float
    entry_time: dt.datetime
    exit_price: float | None
    exit_time: dt.datetime | None
    pnl: float | None
    source_suggestion_id: str


class PaperTradeStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def insert_trade(self, record: PaperTradeRecord) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO paper_trades "
                "(ticker, side, qty, entry_price, entry_time, exit_price, "
                "exit_time, pnl, source_suggestion_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    record.ticker, record.side, record.qty, record.entry_price,
                    record.entry_time.isoformat(),
                    record.exit_price,
                    record.exit_time.isoformat() if record.exit_time else None,
                    record.pnl, record.source_suggestion_id,
                ),
            )
            return int(cur.lastrowid)

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_time: dt.datetime,
        pnl: float,
    ) -> None:
        # Guard against double-close / unknown id: an already-closed or missing
        # trade must not silently overwrite a recorded exit (Spec §8.1 honesty).
        with self._connect() as con:
            cur = con.execute(
                "UPDATE paper_trades SET exit_price = ?, exit_time = ?, pnl = ? "
                "WHERE id = ? AND exit_price IS NULL",
                (exit_price, exit_time.isoformat(), pnl, trade_id),
            )
            if cur.rowcount != 1:
                raise ValueError(
                    f"close_trade affected {cur.rowcount} rows for id={trade_id} "
                    "(unknown id or already closed)"
                )

    def read_trades(self, open_only: bool = False) -> list[StoredPaperTrade]:
        query = (
            "SELECT id, ticker, side, qty, entry_price, entry_time, exit_price, "
            "exit_time, pnl, source_suggestion_id FROM paper_trades"
        )
        if open_only:
            query += " WHERE exit_price IS NULL"
        query += " ORDER BY id"
        with self._connect() as con:
            rows = con.execute(query).fetchall()
        return [
            StoredPaperTrade(
                id=row[0], ticker=row[1], side=row[2], qty=row[3],
                entry_price=row[4],
                entry_time=dt.datetime.fromisoformat(row[5]),
                exit_price=row[6],
                exit_time=dt.datetime.fromisoformat(row[7]) if row[7] else None,
                pnl=row[8], source_suggestion_id=row[9],
            )
            for row in rows
        ]
