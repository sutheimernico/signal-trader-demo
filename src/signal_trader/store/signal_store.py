"""SQLite persistence for the Signal datamodel (Spec §9).

Mirrors PriceBarStore's pattern. Every signal carries timestamp_event (when
it happened) AND timestamp_known (when an outsider could act on it) plus the
price at the known date — the point-in-time anchor for forward returns. Dedup
key is (source, ticker, timestamp_known, accession_no) so re-ingesting the same
filings is idempotent. raw_payload is stored as JSON for auditability.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_LOG = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    source          TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    direction       TEXT NOT NULL,
    timestamp_event TEXT NOT NULL,
    timestamp_known TEXT NOT NULL,
    price_at_known  REAL,
    raw_payload     TEXT NOT NULL,
    confidence      REAL NOT NULL,
    accession_no    TEXT NOT NULL,
    PRIMARY KEY (source, ticker, timestamp_known, accession_no)
);

CREATE TABLE IF NOT EXISTS source_scores (
    source             TEXT NOT NULL,
    window             TEXT NOT NULL,
    n_signals          INTEGER NOT NULL,
    hit_rate           REAL NOT NULL,
    avg_forward_return REAL NOT NULL,
    avg_data_lag_days  REAL NOT NULL,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (source, window)
);
"""


@dataclass(frozen=True)
class SignalRecord:
    ticker: str
    source: str
    signal_type: str
    direction: str
    timestamp_event: dt.date
    timestamp_known: dt.date
    price_at_known: float | None
    raw_payload: dict
    confidence: float

    @property
    def accession_no(self) -> str:
        return str(self.raw_payload.get("accession_no", ""))


@dataclass(frozen=True)
class SourceScoreRecord:
    source: str
    window: str
    n_signals: int
    hit_rate: float
    avg_forward_return: float
    avg_data_lag_days: float


@dataclass(frozen=True)
class StoredSignal:
    ticker: str
    source: str
    signal_type: str
    direction: str
    timestamp_event: dt.date
    timestamp_known: dt.date
    price_at_known: float | None
    raw_payload_json: str
    confidence: float


class SignalStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def insert_signals(self, records: list[SignalRecord]) -> None:
        if not records:
            return
        rows = [
            (
                r.source, r.ticker, r.signal_type, r.direction,
                r.timestamp_event.isoformat(), r.timestamp_known.isoformat(),
                r.price_at_known, json.dumps(r.raw_payload, sort_keys=True),
                r.confidence, r.accession_no,
            )
            for r in records
        ]
        with self._connect() as con:
            cur = con.executemany(
                "INSERT OR IGNORE INTO signals "
                "(source, ticker, signal_type, direction, timestamp_event, "
                "timestamp_known, price_at_known, raw_payload, confidence, "
                "accession_no) VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            inserted = cur.rowcount
            ignored = len(rows) - inserted
            if ignored > 0:
                _LOG.info(
                    "%d signal(s) already existed and were left unchanged (INSERT OR IGNORE)",
                    ignored,
                )

    def read_signals(
        self,
        source: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[StoredSignal]:
        query = (
            "SELECT ticker, source, signal_type, direction, timestamp_event, "
            "timestamp_known, price_at_known, raw_payload, confidence "
            "FROM signals WHERE source = ?"
        )
        params: list[object] = [source]
        if start is not None:
            query += " AND timestamp_known >= ?"
            params.append(start)
        if end is not None:
            query += " AND timestamp_known <= ?"
            params.append(end)
        query += " ORDER BY timestamp_known, ticker"
        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
        return [
            StoredSignal(
                ticker=row[0], source=row[1], signal_type=row[2], direction=row[3],
                timestamp_event=dt.date.fromisoformat(row[4]),
                timestamp_known=dt.date.fromisoformat(row[5]),
                price_at_known=row[6],
                raw_payload_json=row[7],
                confidence=row[8],
            )
            for row in rows
        ]

    def upsert_source_score(self, record: SourceScoreRecord) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO source_scores "
                "(source, window, n_signals, hit_rate, avg_forward_return, "
                "avg_data_lag_days) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source, window) DO UPDATE SET "
                "n_signals=excluded.n_signals, hit_rate=excluded.hit_rate, "
                "avg_forward_return=excluded.avg_forward_return, "
                "avg_data_lag_days=excluded.avg_data_lag_days, "
                "updated_at=datetime('now')",
                (
                    record.source, record.window, record.n_signals,
                    record.hit_rate, record.avg_forward_return,
                    record.avg_data_lag_days,
                ),
            )

    def read_source_scores(self) -> list[SourceScoreRecord]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT source, window, n_signals, hit_rate, avg_forward_return, "
                "avg_data_lag_days FROM source_scores ORDER BY source, window"
            ).fetchall()
        return [
            SourceScoreRecord(
                source=r[0], window=r[1], n_signals=r[2], hit_rate=r[3],
                avg_forward_return=r[4], avg_data_lag_days=r[5],
            )
            for r in rows
        ]
