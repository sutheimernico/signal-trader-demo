"""CLI: fetch the universe (or given tickers) once and cache it.

    uv run python scripts/backfill.py --tickers AAPL MSFT
    uv run python scripts/backfill.py --limit 50
"""
from __future__ import annotations

import argparse

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.market_data.universe import load_sp500_tickers
from signal_trader.store.cache_service import CacheService


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill daily bars into cache")
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", default=config.DEFAULT_START)
    parser.add_argument("--end", default=config.DEFAULT_END)
    args = parser.parse_args()

    tickers = args.tickers or load_sp500_tickers(limit=args.limit)
    service = CacheService(
        YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH
    )
    service.backfill(tickers, args.start, args.end)
    print(f"Cached {len(tickers)} ticker(s) into {config.PARQUET_DIR}")


if __name__ == "__main__":
    main()
