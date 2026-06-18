"""Controller-only LIVE SEC smoke: fetch a handful of real Form 4 filings.

NEVER run in pytest — it contacts SEC EDGAR. Requires SEC_IDENTITY in .env
(format "Name email@example.com"). The controller runs this separately to
confirm the edgartools wiring against the live endpoint:

    uv run python scripts/sec_smoke.py --ticker AAPL --start 2024-01-01 --end 2024-03-31
"""
from __future__ import annotations

import argparse

from signal_trader import config
from signal_trader.sources.edgar_form4 import EdgarForm4Source


def main() -> None:
    parser = argparse.ArgumentParser(description="Live SEC Form 4 smoke test")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    identity = config.sec_identity()
    if not identity:
        raise SystemExit("Set SEC_IDENTITY in .env before running the live smoke")
    source = EdgarForm4Source(identity=identity)
    observations = source.fetch([args.ticker], args.start, args.end)
    print(f"Fetched {len(observations)} insider observation(s) for {args.ticker}")
    for o in observations[:5]:
        print(
            f"  {o.timestamp_known} known | {o.timestamp_event} event | "
            f"{o.transaction_code} {o.acquired_disposed} {o.shares}@{o.price} "
            f"10b5-1={o.is_10b5_1}"
        )


if __name__ == "__main__":
    main()
