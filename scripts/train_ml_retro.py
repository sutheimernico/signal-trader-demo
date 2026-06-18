"""Retroactive ML training on a BROAD universe + LONG history, evaluated honestly.

The first ML run lost to momentum on only 84 OOS points (14 tickers, 2y) — too
little to conclude anything. This trains/evaluates on ~70 liquid names over many
years (thousands of OOS rebalances) so the verdict has real statistical power.
Still purged + embargoed walk-forward, after costs, vs the momentum baseline —
the answer is reported honestly whether or not the model wins.

Uses an ISOLATED cache (data/ml_bars, data/ml_cache.sqlite) so it can run without
touching the production signal DB.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.backtest.costs import CostModel
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.store.cache_service import CacheService
from signal_trader.strategy.shortterm.evaluate import evaluate_ml
from signal_trader.strategy.shortterm.model import GBDTForecaster

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "CRM",
    "ADBE", "INTC", "AMD", "QCOM", "CSCO", "IBM", "TXN", "NOW", "INTU", "AMAT",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "SCHW", "BLK", "SPGI",
    "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "PSX", "MPC", "VLO", "WMB",
    "JNJ", "PFE", "MRK", "ABBV", "UNH", "LLY", "TMO", "ABT", "BMY", "AMGN",
    "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "NKE", "SBUX", "LOW",
    "CAT", "DE", "BA", "HON", "GE", "LMT", "UNP", "UPS", "RTX", "MMM",
    "DIS", "NFLX", "VZ", "T", "CMCSA",
]


def _load(cache: CacheService, tickers, start, end) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            cache.backfill([t], start, end)
            wide = cache.load_close_matrix([t], start, end)
            if t in wide:
                s = wide[t].dropna()
                if len(s) > 300:
                    out[t] = s
        except Exception:  # noqa: BLE001 - skip names with no/short history
            continue
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Retroactive ML training + honest OOS")
    parser.add_argument("--start", default="2012-01-01")
    parser.add_argument("--end", default="2026-06-18")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--n-splits", type=int, default=10)
    parser.add_argument("--test-size", type=int, default=63)
    args = parser.parse_args()

    cache = CacheService(
        YFinanceProvider(),
        config.DATA_DIR / "ml_bars",
        config.DATA_DIR / "ml_cache.sqlite",
    )
    print(f"Backfilling {len(UNIVERSE)} tickers {args.start}..{args.end} (isolated cache)…")
    universe = _load(cache, UNIVERSE, args.start, args.end)
    print(f"Loaded {len(universe)} tickers with sufficient history.")

    cost = CostModel(commission_per_trade=0.001, slippage=0.0005)
    res = evaluate_ml(
        universe, horizon=args.horizon, feature_windows=[5, 10, 20, 60],
        n_splits=args.n_splits, test_size=args.test_size, top_k=args.top_k,
        cost_model=cost, forecaster_factory=GBDTForecaster,
    )
    verdict = "BEAT" if res["beat_baseline"] else "did NOT beat"
    print("\n=== Retro ML training — honest OOS (after costs, vs momentum) ===")
    print(f"universe={len(universe)} tickers  rebalances={res['n_rebalances']}")
    print(f"ML       mean net/rebal={res['ml_mean_net']:.5f}  PSR={res['ml_psr']:.3f}")
    print(f"Baseline mean net/rebal={res['baseline_mean_net']:.5f}  PSR={res['baseline_psr']:.3f}")
    print(f"=> ML {verdict} the momentum baseline after costs (OOS).")


if __name__ == "__main__":
    main()
