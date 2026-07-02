"""CLI: run the momentum baseline through BOTH engines and print the
foundation report (after-cost metrics + benchmark + the vectorized-vs-
event-driven gap).

    uv run python scripts/run_backtest.py --ticker AAPL --lookback 50
"""
from __future__ import annotations

import argparse

from signal_trader import config
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.metrics import per_period_sharpe
from signal_trader.backtest.report import build_foundation_report
from signal_trader.backtest.trial_log import load_trial_sharpes, log_trial
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.store.cache_service import CacheService

# Trial family for the Deflated Sharpe Ratio (backtest/metrics.py): every
# run of this CLI, on any ticker/lookback, counts as one trial in the SAME
# comparable "foundation backtest" search.
_TRIAL_FAMILY = "foundation_backtest"


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

    cost_model = CostModel(commission_per_trade=args.commission, slippage=args.slippage)
    report = build_foundation_report(close, cost_model, lookback=args.lookback)

    # Log this run as one trial (vectorbt engine, representative of the
    # single underlying strategy both engines execute), then re-render WITH
    # the Deflated Sharpe Ratio computed from the full trial history so far.
    vectorbt_returns = report.engine_returns["vectorbt"]
    log_trial(
        config.TRIAL_LOG_PATH,
        family=_TRIAL_FAMILY,
        label=f"ticker={args.ticker} lookback={args.lookback} "
        f"commission={args.commission} slippage={args.slippage}",
        sharpe=per_period_sharpe(vectorbt_returns),
        n_obs=len(vectorbt_returns),
    )
    trial_sharpes = load_trial_sharpes(config.TRIAL_LOG_PATH, family=_TRIAL_FAMILY)
    report = build_foundation_report(
        close, cost_model, lookback=args.lookback, trial_sharpes=trial_sharpes
    )
    print(report.render())
    print(
        f"\n(DSR based on {len(trial_sharpes)} trial(s) logged for "
        f"'{_TRIAL_FAMILY}' so far — see {config.TRIAL_LOG_PATH})"
    )


if __name__ == "__main__":
    main()
