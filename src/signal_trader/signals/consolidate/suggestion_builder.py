"""Build Suggestions from persisted signals (Spec §9, §8.8).

Reads stored signals for a source, consolidates them per ticker, and writes one
open Suggestion per ticker. The system only PROPOSES — the user decides
(Spec §8.8), so every suggestion starts status="open". Point-in-time:
created_at == latest_known == the most recent contributing filing date, the
earliest an outsider could act on the consolidated view; no trade date leaks in.
Re-running is idempotent via the store's (ticker, created_at) dedup.
"""
from __future__ import annotations

import json

from signal_trader.signals.consolidate.consolidate import consolidate_per_ticker
from signal_trader.store.signal_store import SignalStore
from signal_trader.store.suggestion_store import SuggestionRecord, SuggestionStore


def build_suggestions(
    signal_store: SignalStore,
    suggestion_store: SuggestionStore,
    source: str,
    start: str | None = None,
    end: str | None = None,
    horizon: str = "long",
) -> int:
    """Consolidate stored signals into open Suggestions. Returns count written."""
    signals = signal_store.read_signals(source=source, start=start, end=end)
    consolidated = consolidate_per_ticker(signals)
    payload_by_ticker = _payload_by_ticker(signals)
    records = [
        SuggestionRecord(
            ticker=c.ticker,
            consolidated_score=c.consolidated_score,
            contributing_signals={
                "source": source,
                "n_contributing": c.n_contributing,
                # WHO bought: distinct insider names + count, and the EDGAR
                # filing links — so the suggestion shows who and is auditable.
                "insiders": payload_by_ticker.get(c.ticker, {}).get("owners", []),
                "n_insiders": payload_by_ticker.get(c.ticker, {}).get("n_insiders", 0),
                "sources": payload_by_ticker.get(c.ticker, {}).get("sources", []),
            },
            created_at=c.latest_known,
            latest_known=c.latest_known,
            horizon=horizon,
        )
        for c in consolidated.values()
    ]
    suggestion_store.insert_suggestions(records)
    return len(records)


def _payload_by_ticker(signals) -> dict[str, dict]:
    """Per ticker, gather the distinct insider names + EDGAR source links the
    contributing signals carry (from raw_payload)."""
    owners: dict[str, set[str]] = {}
    urls: dict[str, set[str]] = {}
    for s in signals:
        try:
            payload = json.loads(s.raw_payload_json)
        except (ValueError, TypeError):
            continue
        owners.setdefault(s.ticker, set()).update(payload.get("owners") or [])
        urls.setdefault(s.ticker, set()).update(payload.get("sources") or [])
    out: dict[str, dict] = {}
    for ticker in set(owners) | set(urls):
        names = sorted(owners.get(ticker, set()))
        out[ticker] = {
            "owners": names,
            "n_insiders": len(names),
            "sources": sorted(urls.get(ticker, set())),
        }
    return out
