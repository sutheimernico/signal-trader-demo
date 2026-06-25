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
import datetime as dt
import json

import pandas as pd

from signal_trader import config
from signal_trader.backtest.costs import CostModel
from signal_trader.market_data.delistings import load_delistings_csv
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.paper.alpaca.broker_adapter import AlpacaPaperBroker
from signal_trader.paper.ml_loop import open_ml_positions
from signal_trader.store.cache_service import CacheService
from signal_trader.store.paper_trade_store import PaperTradeStore
from signal_trader.store.signal_store import SignalStore
from signal_trader.strategy.shortterm.consensus import ConsensusSignal
from signal_trader.strategy.shortterm.dataset import build_dataset, latest_features
from signal_trader.strategy.shortterm.evaluate import evaluate_ml
from signal_trader.strategy.shortterm.model import GBDTForecaster
from signal_trader.strategy.shortterm.survivorship import DelistingEvent

_FEATURE_WINDOWS = [5, 10, 20]
# Sources persisted by Phase-1/3 ingest; read-only here.
_CONSENSUS_SOURCES = ("insider_form4", "congress_house", "superinvestor_13f")


def _load_close_lookup(tickers: list[str], start: str, end: str) -> dict[str, pd.Series]:
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill(tickers, start, end)
    wide = service.load_close_matrix(tickers, start, end)
    return {t: wide[t].dropna() for t in tickers if t in wide}


def _load_consensus_signals(
    tickers: list[str], start: str, end: str, window_days: int = 30
) -> list[ConsensusSignal]:
    """Read persisted buy signals (point-in-time) for the universe, read-only.

    actor_id is the filing accession number — the most specific distinct-buyer
    id the store carries (see consensus.py). Only known dates are used.

    The read window is widened by ``window_days`` before ``start`` so the
    backward-window count of the earliest evaluation bars is fully populated;
    without it those counts would be silently understated (conservative, but it
    weakens the A/B). ``end`` is kept as-is — never reading past the data range.
    """
    read_start = (dt.date.fromisoformat(start) - dt.timedelta(days=window_days)).isoformat()
    store = SignalStore(config.SQLITE_PATH)
    wanted = set(tickers)
    out: list[ConsensusSignal] = []
    for source in _CONSENSUS_SOURCES:
        for s in store.read_signals(source, start=read_start, end=end):
            if s.ticker not in wanted:
                continue
            accession = str(json.loads(s.raw_payload_json).get("accession_no", ""))
            out.append(
                ConsensusSignal(
                    ticker=s.ticker,
                    timestamp_known=s.timestamp_known,
                    source=s.source,
                    actor_id=accession or f"{s.source}:{s.timestamp_known}",
                )
            )
    return out


def _load_delisting_events(tickers: list[str]) -> list[DelistingEvent]:
    """Load the cached FREE delisting list, restricted to the universe.

    Only names that are in BOTH the universe AND the delisting list can be shaded
    (the documented partial-correction limit), so we filter here to keep the
    scorecard count honest. Missing cache -> empty list (offline-safe).
    """
    wanted = set(tickers)
    return [e for e in load_delistings_csv(config.DELISTINGS_CSV) if e.ticker in wanted]


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
    parser.add_argument(
        "--consensus", action="store_true",
        help="opt in the point-in-time insider/congress/fund consensus feature "
             "(default OFF); runs the SAME OOS A/B with the extra column",
    )
    parser.add_argument("--consensus-window", type=int, default=30,
                        help="backward window (CALENDAR days) for the consensus count")
    parser.add_argument(
        "--survivorship-stress", action="store_true",
        help="opt in the FREE synthetic-delisting robustness test (default OFF): "
             "punish any universe name on/after its SEC-filed delisting with "
             "--delisting-haircut, then re-run the SAME OOS walk-forward",
    )
    parser.add_argument(
        "--delisting-haircut", type=float, default=-0.60,
        help="forward-return assigned to a delisted name's picks (e.g. -0.60; "
             "-1.0 = total loss). Transparent assumption — sweep it for a band",
    )
    args = parser.parse_args()

    cost = CostModel(commission_per_trade=args.commission, slippage=args.slippage)
    universe = _load_close_lookup(args.tickers, args.start, args.end)

    consensus_signals = (
        _load_consensus_signals(
            args.tickers, args.start, args.end, window_days=args.consensus_window
        )
        if args.consensus else None
    )
    feature_mode = (
        f"+consensus (window={args.consensus_window}d, "
        f"{len(consensus_signals)} signals)"
        if args.consensus else "price-only"
    )

    delisting_events = (
        _load_delisting_events(args.tickers) if args.survivorship_stress else None
    )
    delisting_haircut = args.delisting_haircut if args.survivorship_stress else None

    res = evaluate_ml(
        universe, horizon=args.horizon, feature_windows=_FEATURE_WINDOWS,
        n_splits=args.n_splits, test_size=args.test_size, top_k=args.top_k,
        cost_model=cost, forecaster_factory=GBDTForecaster,
        consensus_signals=consensus_signals,
        consensus_window_days=args.consensus_window,
        delisting_events=delisting_events,
        delisting_haircut=delisting_haircut,
    )
    verdict = "BEAT" if res["beat_baseline"] else "did NOT beat"
    shift = res["ml_shift_test"]
    collapse_note = (
        "edge collapses under +1 bar lag (timing-leak suspect)"
        if shift["collapsed"]
        else "no material collapse"
    )
    lines = [
        "=== ML experiment (OOS, after costs — honest measurement, not edge) ===",
        f"features={feature_mode}",
        f"rebalances={res['n_rebalances']}  horizon={args.horizon}  top_k={args.top_k}",
        f"ML       mean net/rebal={res['ml_mean_net']:.4f}  PSR={res['ml_psr']:.3f}",
        f"Baseline mean net/rebal={res['baseline_mean_net']:.4f}  PSR={res['baseline_psr']:.3f}",
        f"=> ML {verdict} the momentum baseline after costs.",
        "--- honesty checks (the only believable figures) ---",
        f"diff-PSR (ML-baseline vs 0)={res['diff_psr']:.3f}  "
        "(>0.5 = ML robustly ahead; absolute PSR above is regime-inflated)",
        f"shift-test (ML picks, +1 bar): Sharpe {shift['baseline']:.2f} -> "
        f"{shift['shifted']:.2f}  [{collapse_note}]",
        f"deflated-Sharpe note: {res['n_configs_tested']} configuration(s) tested; "
        "with multiple windows/configs the absolute PSR overstates significance "
        "(no formal DSR gate — broad-search territory).",
    ]
    if args.survivorship_stress:
        lines += [
            "--- survivorship stress (FREE synthetic-delisting test) ---",
            f"haircut={res['delisting_haircut']:.2f} applied point-in-time to "
            f"{res['n_delisted_in_universe']} universe name(s) on/after their "
            "SEC-filed delisting.",
            f"shaded-pick rate: ML {res['ml_shaded_pick_rate']:.1%} vs baseline "
            f"{res['baseline_shaded_pick_rate']:.1%} — a higher rate means more "
            "exposure to the fragile (delisted) names; the gap, not absolute "
            "returns, is what 'beats baseline under stress' actually measures.",
            "PARTIAL & conservative: only names in BOTH the universe AND the free "
            "SEC delisting list can be shaded; a clean test needs paid delisted "
            "prices (CRSP/Sharadar — Needs Nico). Form 25 mixes M&A/voluntary with "
            "bankruptcy, so a shaded name 'left the listing', not 'went bankrupt'.",
        ]
        if res["n_delisted_in_universe"] == 0:
            lines.append(
                "NOTE: 0 universe names matched the cached delisting list — refresh "
                "data/delistings.csv (scripts/ingest_delistings.py) or widen the "
                "universe to include names that later delisted."
            )

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
