"""CLI: ingest US House congressional PURCHASES -> consensus signals (free, PIT).

    uv run python scripts/ingest_congress.py --years 2026 2025 --max-filings 120

Only multi-member consensus (>=2 distinct congresspeople buying the same ticker)
becomes a dashboard suggestion; single-member buys stay as recorded signals.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.signals.congress.pipeline import SOURCE_NAME, persist_congress_signals
from signal_trader.signals.consolidate.suggestion_builder import build_suggestions
from signal_trader.sources.congress_trades import CongressTradesSource
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
        except Exception:  # no price data/history for this name; skip it
            continue
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest House congressional buys")
    parser.add_argument("--years", nargs="+", default=["2026"])
    parser.add_argument("--max-filings", type=int, default=120)
    parser.add_argument("--price-start", default="2023-01-01")
    parser.add_argument("--end", default=config.DEFAULT_END)
    args = parser.parse_args()

    obs = CongressTradesSource().fetch_recent_purchases(args.years, max_filings=args.max_filings)
    tickers = sorted({o.ticker for o in obs})
    counts: dict[str, set] = {}
    for o in obs:
        counts.setdefault(o.ticker, set()).add(o.member)
    consensus = sorted(t for t, m in counts.items() if len(m) >= 2)
    print(
        f"{len(obs)} buys across {len(tickers)} tickers; "
        f"{len(consensus)} with >=2-member consensus: {consensus}"
    )
    close_lookup = _load_close_lookup(consensus, args.price_start, args.end)
    store = SignalStore(config.SQLITE_PATH)
    n = persist_congress_signals(obs, close_lookup, store)
    n_sug = build_suggestions(
        store, SuggestionStore(config.SQLITE_PATH), source=SOURCE_NAME, min_buyers=2
    )
    print(f"Persisted {n} congress signal(s); {n_sug} consensus suggestion(s)")


if __name__ == "__main__":
    main()
