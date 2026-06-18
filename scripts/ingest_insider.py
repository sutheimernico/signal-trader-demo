"""CLI: ingest Form 4 -> filter -> persist insider signals (point-in-time).

    uv run python scripts/ingest_insider.py --tickers AAPL MSFT \
        --start 2024-01-01 --end 2024-12-31

EdgarForm4Source is faked in tests; the only live SEC contact is sec_smoke.py.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.signals.insider.pipeline import build_insider_signals
from signal_trader.sources.edgar_form4 import EdgarForm4Source
from signal_trader.store.cache_service import CacheService
from signal_trader.store.signal_store import SignalStore


def _load_close_lookup(
    tickers: list[str], start: str, end: str
) -> dict[str, pd.Series]:
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill(tickers, start, end)
    wide = service.load_close_matrix(tickers, start, end)
    return {t: wide[t].dropna() for t in tickers}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest insider Form 4 signals")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--min-insiders", type=int, default=3)
    args = parser.parse_args()

    source = EdgarForm4Source(identity=config.sec_identity())
    close_lookup = _load_close_lookup(args.tickers, args.start, args.end)
    store = SignalStore(config.SQLITE_PATH)
    n = build_insider_signals(
        source, args.tickers, args.start, args.end,
        close_lookup=close_lookup, store=store,
        window_days=args.window_days, min_insiders=args.min_insiders,
    )
    print(f"Persisted {n} insider signal(s) into {config.SQLITE_PATH}")


if __name__ == "__main__":
    main()
