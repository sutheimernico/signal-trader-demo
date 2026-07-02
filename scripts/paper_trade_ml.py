"""Autonomous ML paper-trading cycle: train on history, buy today's top-k.

Real markets, real prices, DEMO money (Alpaca paper). One cycle: train the GBDT
on the cached broad universe, score today's point-in-time features, and open the
top-k predicted names as Alpaca PAPER orders (no confirmation). Idempotent per
(ticker, date). Practice/plumbing — the ML edge is NOT survivorship-verified, so
this is for paper practice only, never a real-money signal.

Run during market hours so market orders fill immediately:
    uv run python scripts/paper_trade_ml.py --top-k 5 --qty 2
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.paper.alpaca.broker_adapter import AlpacaPaperBroker
from signal_trader.paper.ml_loop import open_ml_positions
from signal_trader.store.cache_service import CacheService
from signal_trader.store.paper_trade_store import PaperTradeStore
from signal_trader.strategy.shortterm.dataset import build_dataset, latest_features
from signal_trader.strategy.shortterm.model import GBDTForecaster

_FEATURE_WINDOWS = [5, 10, 20, 60]


def _load(cache: CacheService, tickers: list[str], start: str, end: str) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            cache.backfill([t], start, end)
            wide = cache.load_close_matrix([t], start, end)
            if t in wide and len(wide[t].dropna()) > 300:
                out[t] = wide[t].dropna()
        except Exception:  # skip names without history
            continue
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous ML paper-trade cycle")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=config.DEFAULT_END)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--qty", type=float, default=2.0)
    args = parser.parse_args()

    from scripts.train_ml_retro import UNIVERSE

    cache = CacheService(
        YFinanceProvider(), config.DATA_DIR / "ml_bars", config.DATA_DIR / "ml_cache.sqlite"
    )
    universe = _load(cache, UNIVERSE, args.start, args.end)
    Xtr, ytr = build_dataset(universe, horizon=args.horizon, feature_windows=_FEATURE_WINDOWS)
    model = GBDTForecaster()
    model.fit(Xtr, ytr)
    latest = latest_features(universe, feature_windows=_FEATURE_WINDOWS)

    key, secret = config.alpaca_credentials()
    broker = AlpacaPaperBroker(api_key=key, secret_key=secret)
    store = PaperTradeStore(config.SQLITE_PATH)
    opened = open_ml_positions(latest, model, store, broker, top_k=args.top_k, qty=args.qty)
    picks = latest.assign(score=model.predict(latest)).sort_values("score", ascending=False)
    top = [t for (t, _) in picks.index[: args.top_k]]
    print(f"ML paper cycle: trained on {len(universe)} names; top-{args.top_k} = {top}")
    print(f"Opened {opened} new paper position(s) (demo money, real prices).")


if __name__ == "__main__":
    main()
