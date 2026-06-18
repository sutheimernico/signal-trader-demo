"""SQLite persistence for Suggestion (Spec §9).

A Suggestion is the system's proposal for a ticker, built from consolidated
signals; in Track 1 the USER decides — the system only proposes (Spec §8.8).
Point-in-time: created_at/latest_known come from signal timestamp_known, never
a trade date. Dedup key is (ticker, created_at) so re-running the builder over
the same window is idempotent. contributing_signals is stored as JSON for audit.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS suggestions (
    ticker               TEXT NOT NULL,
    consolidated_score   REAL NOT NULL,
    contributing_signals TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    latest_known         TEXT NOT NULL,
    horizon              TEXT NOT NULL,
    status               TEXT NOT NULL,
    user_decision        TEXT,
    decided_at           TEXT,
    PRIMARY KEY (ticker, created_at)
);
"""


@dataclass(frozen=True)
class SuggestionRecord:
    ticker: str
    consolidated_score: float
    contributing_signals: dict
    created_at: dt.date
    latest_known: dt.date
    horizon: str
    status: str = "open"


@dataclass(frozen=True)
class StoredSuggestion:
    ticker: str
    consolidated_score: float
    contributing_signals_json: str
    created_at: dt.date
    latest_known: dt.date
    horizon: str
    status: str
    user_decision: str | None
    decided_at: dt.date | None


class SuggestionStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def insert_suggestions(self, records: list[SuggestionRecord]) -> None:
        if not records:
            return
        rows = [
            (
                r.ticker, r.consolidated_score,
                json.dumps(r.contributing_signals, sort_keys=True),
                r.created_at.isoformat(), r.latest_known.isoformat(),
                r.horizon, r.status,
            )
            for r in records
        ]
        with self._connect() as con:
            con.executemany(
                "INSERT OR IGNORE INTO suggestions "
                "(ticker, consolidated_score, contributing_signals, created_at, "
                "latest_known, horizon, status) VALUES (?,?,?,?,?,?,?)",
                rows,
            )

    def record_decision(
        self,
        ticker: str,
        created_at: dt.date,
        decision: str,
        decided_at: dt.date,
    ) -> None:
        with self._connect() as con:
            cur = con.execute(
                "UPDATE suggestions SET status = ?, user_decision = ?, "
                "decided_at = ? WHERE ticker = ? AND created_at = ?",
                (decision, decision, decided_at.isoformat(), ticker,
                 created_at.isoformat()),
            )
            if cur.rowcount == 0:
                raise ValueError(
                    f"no suggestion for ({ticker}, {created_at}); decision lost"
                )

    def read_suggestions(
        self, status: str | None = None
    ) -> list[StoredSuggestion]:
        query = (
            "SELECT ticker, consolidated_score, contributing_signals, created_at, "
            "latest_known, horizon, status, user_decision, decided_at "
            "FROM suggestions"
        )
        params: list[object] = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at, ticker"
        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
        return [
            StoredSuggestion(
                ticker=row[0], consolidated_score=row[1],
                contributing_signals_json=row[2],
                created_at=dt.date.fromisoformat(row[3]),
                latest_known=dt.date.fromisoformat(row[4]),
                horizon=row[5], status=row[6], user_decision=row[7],
                decided_at=dt.date.fromisoformat(row[8]) if row[8] else None,
            )
            for row in rows
        ]
