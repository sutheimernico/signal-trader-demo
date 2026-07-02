"""CLI: MARKET-WIDE insider Form 4 scan (no hand-picked tickers).

    uv run python scripts/scan_insider_market.py --start 2026-03-01 --end 2026-06-18

Scans every Form 4 in the window, funnels to the issuers with the most filings
(candidate clusters), parses only those, then runs the same purchase + cluster
filters to surface fresh >=N-insider open-market BUY clusters across the whole
market. Best-effort pricing; honest about how many issuers were skipped.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.signals.consolidate.suggestion_builder import build_suggestions
from signal_trader.signals.insider.pipeline import SOURCE_NAME, persist_insider_signals
from signal_trader.sources.edgar_form4 import EdgarForm4Source
from signal_trader.store.cache_service import CacheService
from signal_trader.store.signal_store import SignalStore
from signal_trader.store.suggestion_store import SuggestionStore


def _load_close_lookup(tickers: list[str], start: str, end: str) -> dict[str, pd.Series]:
    if not tickers:
        return {}
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    out: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            service.backfill([t], start, end)
            wide = service.load_close_matrix([t], start, end)
            if t in wide:
                out[t] = wide[t].dropna()
        except Exception:  # no price data for this name; skip it
            continue
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Market-wide insider Form 4 scan")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--min-filings", type=int, default=6)
    parser.add_argument("--max-candidates", type=int, default=200)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--min-insiders", type=int, default=3)
    parser.add_argument("--price-start", default="2023-01-01")
    args = parser.parse_args()

    source = EdgarForm4Source(identity=config.sec_identity())
    obs = source.fetch_market_wide(
        args.start, args.end,
        min_filings=args.min_filings, max_candidates=args.max_candidates,
    )
    tickers = sorted({o.ticker for o in obs if o.ticker})
    print(f"Market scan parsed {len(obs)} observation(s) across {len(tickers)} issuer(s)")
    close_lookup = _load_close_lookup(tickers, args.price_start, args.end)
    store = SignalStore(config.SQLITE_PATH)
    n = persist_insider_signals(
        obs, close_lookup, store,
        window_days=args.window_days, min_insiders=args.min_insiders,
    )
    n_sug = build_suggestions(store, SuggestionStore(config.SQLITE_PATH), source=SOURCE_NAME)
    print(f"Persisted {n} new cluster signal(s); {n_sug} insider suggestion(s) total")


if __name__ == "__main__":
    main()
