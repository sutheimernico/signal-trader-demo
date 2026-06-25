"""CLI: refresh the FREE delisting list from SEC EDGAR full-text search.

    uv run python scripts/ingest_delistings.py --start 2015-01-01 --end 2026-06-30

The ONLY live SEC contact for delistings (like sec_smoke.py — never in pytest).
Pages EDGAR full-text search for Form 25-NSE / 25 filings, extracts ticker +
filing date, and writes the offline cache the survivorship stress test reads
(data/delistings.csv). Needs SEC_IDENTITY in .env (SEC fair access requires a
contactable User-Agent and caps requests at ~10/s — the fetcher throttles).

Honest scope: Form 25 delistings mix voluntary delistings / M&A with bankruptcy,
so the list is "names that left the listing", not "bankruptcies". For a
survivorship-bias stress test that is exactly right (we want every name that left
the universe).
"""
from __future__ import annotations

import argparse

from signal_trader import config
from signal_trader.market_data.delistings import fetch_delistings, save_delistings_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the free SEC delisting list")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--forms", nargs="+", default=["25-NSE", "25"],
        help="SEC delisting form types to scan (default: 25-NSE 25)",
    )
    args = parser.parse_args()

    identity = config.sec_identity()
    if not identity:
        raise SystemExit(
            "SEC_IDENTITY unset — set it in .env (e.g. 'Name email@host'); "
            "refusing to contact SEC anonymously."
        )

    events = fetch_delistings(
        forms=tuple(args.forms), start=args.start, end=args.end, identity=identity,
    )
    save_delistings_csv(events, config.DELISTINGS_CSV)
    print(f"Wrote {len(events)} delisting record(s) to {config.DELISTINGS_CSV}")


if __name__ == "__main__":
    main()
