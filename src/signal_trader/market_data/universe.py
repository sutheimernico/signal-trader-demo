"""S&P-500 universe from a bundled, committed snapshot CSV.

Deterministic by design: we read a frozen constituent list rather than
scraping live, so backtests are reproducible. CAVEAT: survivorship bias.
This snapshot lists tickers alive at snapshot time only; names that were
delisted or removed from the index before then are absent. No free source
fixes this — treat any aggregate result as survivorship-inflated.
"""
from __future__ import annotations

import csv

from signal_trader.config import SP500_SNAPSHOT


def load_sp500_tickers(limit: int | None = None) -> list[str]:
    """Return Yahoo-style S&P-500 tickers, sorted and unique.

    Survivorship caveat: the snapshot only contains currently-listed members
    (see module docstring). Dotted symbols (BRK.B) are normalized to Yahoo's
    dash form (BRK-B).
    """
    tickers: set[str] = set()
    with SP500_SNAPSHOT.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw = row["ticker"].strip().upper()
            if raw:
                tickers.add(raw.replace(".", "-"))
    result = sorted(tickers)
    return result[:limit] if limit is not None else result
