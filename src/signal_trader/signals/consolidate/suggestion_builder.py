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
    sources_by_ticker = _source_links_by_ticker(signals)
    records = [
        SuggestionRecord(
            ticker=c.ticker,
            consolidated_score=c.consolidated_score,
            contributing_signals={
                "source": source,
                "n_contributing": c.n_contributing,
                # EDGAR filing links so the suggestion is auditable to SEC.
                "sources": sources_by_ticker.get(c.ticker, []),
            },
            created_at=c.latest_known,
            latest_known=c.latest_known,
            horizon=horizon,
        )
        for c in consolidated.values()
    ]
    suggestion_store.insert_suggestions(records)
    return len(records)


def _source_links_by_ticker(signals) -> dict[str, list[str]]:
    """Collect the EDGAR source URLs each ticker's signals carry (raw_payload)."""
    out: dict[str, set[str]] = {}
    for s in signals:
        try:
            payload = json.loads(s.raw_payload_json)
        except (ValueError, TypeError):
            continue
        urls = payload.get("sources") or []
        if urls:
            out.setdefault(s.ticker, set()).update(urls)
    return {ticker: sorted(urls) for ticker, urls in out.items()}
