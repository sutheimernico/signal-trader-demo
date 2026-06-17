"""CLI: run the momentum baseline through BOTH engines and print the
foundation report (after-cost metrics + benchmark + the vectorized-vs-
event-driven gap).

    uv run python scripts/run_backtest.py --ticker AAPL --lookback 50
"""
from __future__ import annotations

import argparse

from signal_trader import config
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.report import build_foundation_report
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.store.cache_service import CacheService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the foundation backtest report")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--lookback", type=int, default=50)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--start", default=config.DEFAULT_START)
    parser.add_argument("--end", default=config.DEFAULT_END)
    args = parser.parse_args()

    service = CacheService(
        YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH
    )
    service.backfill([args.ticker], args.start, args.end)
    close = service.load_close_matrix([args.ticker], args.start, args.end)[
        args.ticker
    ].dropna()

    report = build_foundation_report(
        close,
        CostModel(commission_per_trade=args.commission, slippage=args.slippage),
        lookback=args.lookback,
    )
    print(report.render())


if __name__ == "__main__":
    main()
