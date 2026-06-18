"""CLI: forward paper loop — build suggestions, open accepted, close due.

    uv run python scripts/run_forward_paper.py --hold-days 5

PLUMBING VALIDATION, not a performance result (Spec §3, §8.10). Steps:
  1. Build Suggestions from persisted insider signals (point-in-time).
  2. Open paper trades for suggestions the USER has accepted (via the dashboard);
     this CLI never auto-accepts — the human decides (Spec §8.8).
  3. Close paper trades held >= hold-days, using the actual sell fill.

The broker is live Alpaca paper (needs keys in .env); in tests it is faked.
Use --build-only to just refresh suggestions without touching the broker.
"""
from __future__ import annotations

import argparse
import datetime as dt

from signal_trader import config
from signal_trader.paper.alpaca.broker_adapter import AlpacaPaperBroker
from signal_trader.paper.loop import close_due_trades, open_accepted_suggestions
from signal_trader.signals.consolidate.suggestion_builder import build_suggestions
from signal_trader.store.paper_trade_store import PaperTradeStore
from signal_trader.store.signal_store import SignalStore
from signal_trader.store.suggestion_store import SuggestionStore

SOURCE_NAME = "insider_form4"


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward paper loop")
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--qty", type=float, default=1.0)
    parser.add_argument("--horizon", default="long")
    parser.add_argument(
        "--build-only", action="store_true",
        help="only rebuild suggestions; do not contact the broker",
    )
    args = parser.parse_args()

    db = config.SQLITE_PATH
    signals = SignalStore(db)
    suggestions = SuggestionStore(db)
    trades = PaperTradeStore(db)

    n_sug = build_suggestions(
        signals, suggestions, source=SOURCE_NAME, horizon=args.horizon
    )
    lines = [
        "=== Forward paper loop (plumbing validation, not a performance result) ===",
        f"Suggestions in store after build: {n_sug} ticker(s)",
    ]

    if not args.build_only:
        key, secret = config.alpaca_credentials()
        broker = AlpacaPaperBroker(api_key=key, secret_key=secret)
        opened = open_accepted_suggestions(suggestions, trades, broker, qty=args.qty)
        # tz-aware: Alpaca fills are UTC-aware, so as_of must be too or the
        # timedelta subtraction in close_due_trades raises (offset-naive vs aware).
        closed = close_due_trades(
            trades, broker, as_of=dt.datetime.now(tz=dt.UTC),
            hold_days=args.hold_days,
        )
        lines.append(f"Opened {opened} new paper trade(s) from accepted suggestions")
        lines.append(f"Closed {closed} paper trade(s) held >= {args.hold_days} days")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
