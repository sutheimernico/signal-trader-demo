"""CLI: insider strategy through BOTH engines + hit-rates + after-cost benchmark.

    uv run python scripts/run_insider_report.py --tickers AAPL \
        --start 2024-01-01 --end 2024-12-31

Every figure is after costs; the benchmark is buy-and-hold after the SAME costs;
each source's hit-rate AND data-lag are printed (Acceptance §3, §4). Reuses the
Phase-1 engines, cost model, benchmark, and metrics unchanged.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.backtest.benchmark import buy_and_hold_equity
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.metrics import compute_metrics
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.signals.scoring.source_score import score_source
from signal_trader.store.cache_service import CacheService
from signal_trader.store.signal_store import SignalStore
from signal_trader.strategy.longterm.insider_strategy import run_insider_through_engines

SOURCE_NAME = "insider_form4"


def _load_close_lookup(
    tickers: list[str], start: str, end: str
) -> dict[str, pd.Series]:
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill(tickers, start, end)
    wide = service.load_close_matrix(tickers, start, end)
    return {t: wide[t].dropna() for t in tickers}


def main() -> None:
    parser = argparse.ArgumentParser(description="Insider strategy report")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--hold-bars", type=int, default=5)
    parser.add_argument("--horizon", type=int, default=5)
    args = parser.parse_args()

    cost_model = CostModel(
        commission_per_trade=args.commission, slippage=args.slippage
    )
    close_lookup = _load_close_lookup(args.tickers, args.start, args.end)
    store = SignalStore(config.SQLITE_PATH)
    signals = store.read_signals(source=SOURCE_NAME, start=args.start, end=args.end)

    lines = ["=== Insider Report (all figures after costs) ===", ""]
    for ticker in args.tickers:
        close = close_lookup[ticker]
        ticker_signals = [s for s in signals if s.ticker == ticker]
        results = run_insider_through_engines(
            close, ticker_signals, cost_model, hold_bars=args.hold_bars
        )
        for engine, res in results.items():
            m = compute_metrics(res.returns())
            lines.append(
                f"[{ticker}/{engine}] trades={res.n_trades} CAGR={m.cagr:.3f} "
                f"Sharpe={m.sharpe:.3f} Sortino={m.sortino:.3f} "
                f"Calmar={m.calmar:.3f} MaxDD={m.max_drawdown:.3f} PSR={m.psr:.3f}"
            )
        bench = compute_metrics(
            buy_and_hold_equity(close, cost_model).pct_change().dropna()
        )
        lines.append(
            f"[{ticker}/Buy & Hold (after costs)] CAGR={bench.cagr:.3f} "
            f"Sharpe={bench.sharpe:.3f} Sortino={bench.sortino:.3f} "
            f"Calmar={bench.calmar:.3f} MaxDD={bench.max_drawdown:.3f} "
            f"PSR={bench.psr:.3f}"
        )

    score = score_source(
        store, source=SOURCE_NAME, close_lookup=close_lookup,
        horizon=args.horizon, window_label=f"{args.horizon}d", persist=True,
    )
    lines.append("")
    lines.append(
        f"[{SOURCE_NAME}] n_signals={score.n_signals} "
        f"hit_rate={score.hit_rate:.3f} "
        f"avg_forward_return={score.avg_forward_return:.4f} "
        f"data_lag_days={score.avg_data_lag_days:.2f}"
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
