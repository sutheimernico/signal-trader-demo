"""CLI: generate a self-contained HTML tearsheet for a single-ticker
foundation backtest — equity curve, drawdown, monthly heatmap, the honest
metric set (CAGR/Sharpe/Sortino/Calmar/MaxDD/PSR/DSR), and a cost
disclosure. Uses the vectorbt engine (same convention as run_backtest.py's
trial logging).

    uv run python scripts/generate_tearsheet.py --ticker AAPL \
        --start 2020-01-01 --end 2024-01-01

Writes to reports/<ticker>_<start>_<end>_tearsheet.html (gitignored, like
the rest of the local cache — regenerate with this command; open the file
directly in a browser, no server needed).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from signal_trader import config
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.metrics import per_period_sharpe
from signal_trader.backtest.report import build_foundation_report
from signal_trader.backtest.tearsheet import build_tearsheet
from signal_trader.backtest.trial_log import load_trial_sharpes, log_trial
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.store.cache_service import CacheService

# SAME family as run_backtest.py: both are trials in the "foundation backtest"
# search, so they share one honest trial history for the Deflated Sharpe Ratio.
_TRIAL_FAMILY = "foundation_backtest"

# Honesty-rule (repo mandate): a tearsheet must not cherry-pick flattering
# numbers. These notes are always attached, regardless of how this specific
# ticker/lookback performed, so a reader who only opens this one file still
# sees the repo's sober findings, not just this run's headline metrics.
_HONEST_NOTES = [
    "This is a single-ticker momentum-baseline backtest, not a trading "
    "recommendation and not an edge claim — see the project README's "
    "honest-harness framing.",
    "This repo's separate ML experiment (GBDT vs momentum, out-of-sample, "
    "after costs) does NOT robustly beat the momentum baseline (diff-PSR "
    "< 0.5 in every arm tested) — the expected, honest finding, reported "
    "as a learning artifact, not hidden. See README 'Honest harness'.",
    "The vectorbt engine (shown here) and backtesting.py disagree on this "
    "exact same signal — a known realism artifact between a vectorized and "
    "an event-driven engine (see run_backtest.py's report), not an edge.",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an HTML tearsheet for a foundation backtest"
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--lookback", type=int, default=50)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--start", default=config.DEFAULT_START)
    parser.add_argument("--end", default=config.DEFAULT_END)
    parser.add_argument(
        "--output", default=None,
        help="output HTML path (default: reports/<ticker>_<start>_<end>_tearsheet.html)",
    )
    args = parser.parse_args()

    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill([args.ticker], args.start, args.end)
    close = service.load_close_matrix([args.ticker], args.start, args.end)[
        args.ticker
    ].dropna()

    cost_model = CostModel(commission_per_trade=args.commission, slippage=args.slippage)
    report = build_foundation_report(close, cost_model, lookback=args.lookback)

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

    output_path = (
        Path(args.output)
        if args.output
        else config.REPO_ROOT / "reports" / f"{args.ticker}_{args.start}_{args.end}_tearsheet.html"
    )
    build_tearsheet(
        returns=report.engine_returns["vectorbt"],
        benchmark=close.pct_change().dropna(),
        metrics_report=report.engine_metrics["vectorbt"],
        cost_model=cost_model,
        title=f"{args.ticker} — Foundation Backtest Tearsheet (vectorbt, after costs)",
        output_path=output_path,
        notes=_HONEST_NOTES,
    )
    print(f"Wrote tearsheet: {output_path}")


if __name__ == "__main__":
    main()
