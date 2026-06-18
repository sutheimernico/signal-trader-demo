"""CLI: ingest famous-investor 13F NEW buys -> consensus signals (point-in-time).

    uv run python scripts/ingest_13f.py            # default famous roster
    uv run python scripts/ingest_13f.py --funds "Scion / Michael Burry"

Follows what famous managers ACTUALLY bought (SEC 13F), long shares only (puts
ignored). ~45-day lag is real and shown by the harness. Then build suggestions.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.signals.consolidate.suggestion_builder import build_suggestions
from signal_trader.signals.superinvestor.pipeline import (
    SOURCE_NAME,
    persist_13f_signals,
)
from signal_trader.sources.superinvestor_13f import FAMOUS_FUNDS, ThirteenFSource
from signal_trader.store.cache_service import CacheService
from signal_trader.store.signal_store import SignalStore
from signal_trader.store.suggestion_store import SuggestionStore


def _load_close_lookup(tickers: list[str], start: str, end: str) -> dict[str, pd.Series]:
    if not tickers:
        return {}
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill(tickers, start, end)
    wide = service.load_close_matrix(tickers, start, end)
    return {t: wide[t].dropna() for t in tickers if t in wide}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest famous-investor 13F buys")
    parser.add_argument("--funds", nargs="+", default=list(FAMOUS_FUNDS))
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default=config.DEFAULT_END)
    args = parser.parse_args()

    source = ThirteenFSource(identity=config.sec_identity())
    observations = source.fetch_new_long_positions(args.funds)
    tickers = sorted({o.ticker for o in observations})
    print(f"Fetched {len(observations)} new long position(s) across {len(tickers)} ticker(s)")
    close_lookup = _load_close_lookup(tickers, args.start, args.end)
    store = SignalStore(config.SQLITE_PATH)
    n = persist_13f_signals(observations, close_lookup, store)
    build_suggestions(store, SuggestionStore(config.SQLITE_PATH), source=SOURCE_NAME)
    print(f"Persisted {n} consensus 13F signal(s) into {config.SQLITE_PATH}")


if __name__ == "__main__":
    main()
