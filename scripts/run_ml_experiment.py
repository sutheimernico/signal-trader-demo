"""CLI: autonomous ML experiment (Phase 4, Track 2) — train, evaluate, paper-trade.

    uv run python scripts/run_ml_experiment.py --tickers AAPL MSFT XOM ... \
        --start 2023-01-01 --end 2024-12-31

Honest measurement: prints an OOS scorecard (after costs, vs the momentum
baseline, with PSR) and says plainly whether ML beat the baseline. Then — unless
--no-trade — trains on all history and opens top-k paper trades autonomously (no
confirmation; paper money only, separate from the human insider track).
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.backtest.costs import CostModel
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.paper.alpaca.broker_adapter import AlpacaPaperBroker
from signal_trader.paper.ml_loop import open_ml_positions
from signal_trader.store.cache_service import CacheService
from signal_trader.store.paper_trade_store import PaperTradeStore
from signal_trader.strategy.shortterm.dataset import build_dataset, latest_features
from signal_trader.strategy.shortterm.evaluate import evaluate_ml
from signal_trader.strategy.shortterm.model import GBDTForecaster

_FEATURE_WINDOWS = [5, 10, 20]


def _load_close_lookup(tickers: list[str], start: str, end: str) -> dict[str, pd.Series]:
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill(tickers, start, end)
    wide = service.load_close_matrix(tickers, start, end)
    return {t: wide[t].dropna() for t in tickers if t in wide}


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous ML paper experiment")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--n-splits", type=int, default=3)
    parser.add_argument("--test-size", type=int, default=21)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--no-trade", action="store_true")
    args = parser.parse_args()

    cost = CostModel(commission_per_trade=args.commission, slippage=args.slippage)
    universe = _load_close_lookup(args.tickers, args.start, args.end)

    res = evaluate_ml(
        universe, horizon=args.horizon, feature_windows=_FEATURE_WINDOWS,
        n_splits=args.n_splits, test_size=args.test_size, top_k=args.top_k,
        cost_model=cost, forecaster_factory=GBDTForecaster,
    )
    verdict = "BEAT" if res["beat_baseline"] else "did NOT beat"
    lines = [
        "=== ML experiment (OOS, after costs — honest measurement, not edge) ===",
        f"rebalances={res['n_rebalances']}  horizon={args.horizon}  top_k={args.top_k}",
        f"ML       mean net/rebal={res['ml_mean_net']:.4f}  PSR={res['ml_psr']:.3f}",
        f"Baseline mean net/rebal={res['baseline_mean_net']:.4f}  PSR={res['baseline_psr']:.3f}",
        f"=> ML {verdict} the momentum baseline after costs.",
    ]

    if not args.no_trade:
        # Train on all labelled history, then act on today's point-in-time features.
        Xtr, ytr = build_dataset(
            universe, horizon=args.horizon, feature_windows=_FEATURE_WINDOWS
        )
        model = GBDTForecaster()
        model.fit(Xtr, ytr)
        latest = latest_features(universe, feature_windows=_FEATURE_WINDOWS)
        key, secret = config.alpaca_credentials()
        broker = AlpacaPaperBroker(api_key=key, secret_key=secret)
        store = PaperTradeStore(config.SQLITE_PATH)
        opened = open_ml_positions(latest, model, store, broker, top_k=args.top_k)
        lines.append(f"Opened {opened} autonomous ML paper trade(s).")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
