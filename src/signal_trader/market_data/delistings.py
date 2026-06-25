"""FREE point-in-time delisting list from SEC EDGAR full-text search.

Source for the survivorship stress test (``strategy/shortterm/survivorship.py``).
SEC EDGAR full-text search returns, per filing, the issuer's ticker (embedded in
``display_names``) and the filing date — for free, no key, no signup. The
delisting form types:
  - ``25-NSE`` — exchange Notification of Removal from Listing (the main signal,
    ~1.2k/yr, clean coverage ~2005-present).
  - ``25`` — issuer-filed removal (covers pre-2005 and voluntary delistings).
The filing date (``file_date``) is the date the delisting became KNOWABLE to an
outsider — exactly the point-in-time anchor the haircut needs (no lookahead).

Honesty caveat baked into the docs: Form 25 delistings mix voluntary delistings
and M&A with bankruptcies, so a listed event means a name "left the listing", NOT
that it went bankrupt. For a survivorship-bias test that is fine (we want every
name that left the universe), but the label must not overclaim.

Design: offline-first. The eval/CLI read a cached CSV
(``load_delistings_csv``) and never touch the network. ``fetch_delistings``
refreshes that cache and is the ONLY network path; it takes an injected
``http_get`` so tests fake it — no live SEC call in pytest. SEC fair access is
honoured: a contactable ``User-Agent`` is mandatory (the endpoint 403s without
one) and the caller must stay <=10 req/s.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from signal_trader.strategy.shortterm.survivorship import DelistingEvent

_LOG = logging.getLogger(__name__)

__all__ = [
    "DelistingEvent",
    "fetch_delistings",
    "load_delistings_csv",
    "parse_fts_hits",
    "save_delistings_csv",
]

_FTS_URL = "https://efts.sec.gov/LATEST/search-index"
# A ticker parenthetical looks like "(ACME)" or "(OXLC, OXLCI, ...)"; a CIK-only
# tail "(CIK 000...)" must NOT match. Tickers: letters, digits, dot/dash; the
# leading token before a comma is the primary class.
_TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9}(?:,\s*[A-Z0-9.\-]+)*)\)")


def _primary_ticker(display_names: list[str]) -> str | None:
    """Extract the primary, Yahoo-normalized ticker from an FTS display name.

    Returns None when only a CIK parenthetical is present (no ticker mapping) —
    such a hit is skipped, never fabricated.
    """
    if not display_names:
        return None
    text = display_names[0]
    for match in _TICKER_RE.finditer(text):
        token = match.group(1).split(",")[0].strip().upper()
        if token == "CIK" or token.startswith("CIK "):
            continue
        if token:
            return token.replace(".", "-")  # BRK.B -> BRK-B (yfinance form)
    return None


def parse_fts_hits(hits: list[dict]) -> list[DelistingEvent]:
    """Map raw EDGAR FTS ``hits.hits[]`` entries to DelistingEvent.

    Hits without a resolvable ticker are dropped (logged-by-omission); a missing
    ticker cannot be invented. The filing ``file_date`` is the point-in-time
    knowable date.
    """
    events: list[DelistingEvent] = []
    for hit in hits:
        src = hit.get("_source", hit)
        ticker = _primary_ticker(src.get("display_names") or [])
        file_date = src.get("file_date")
        if not ticker or not file_date:
            continue
        events.append(
            DelistingEvent(
                ticker=ticker,
                delisted_known=dt.date.fromisoformat(str(file_date)[:10]),
            )
        )
    return events


def _urllib_get(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)  # noqa: S310 - https SEC endpoint
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return resp.read()


def fetch_delistings(
    *,
    forms: tuple[str, ...] = ("25-NSE", "25"),
    start: str,
    end: str,
    identity: str,
    page_size: int = 100,
    max_pages: int = 200,
    http_get: Callable[[str, dict], bytes] | None = None,
    pause_s: float = 0.15,
) -> list[DelistingEvent]:
    """Page the EDGAR FTS endpoint for delisting filings in [start, end].

    ``identity`` MUST be a contactable string (e.g. 'Name email@host') — sent as
    the SEC-required User-Agent. ``http_get`` is injected so tests fake the
    network; production uses urllib (stdlib, no new dep). ``pause_s`` throttles
    under SEC's 10 req/s cap. De-dupes by (ticker, earliest known date).
    """
    if not identity:
        raise ValueError(
            "SEC identity required (set SEC_IDENTITY in .env); refusing to "
            "contact SEC anonymously"
        )
    get = http_get or _urllib_get
    headers = {"User-Agent": identity, "Accept": "application/json"}
    forms_param = ",".join(forms)
    by_ticker: dict[str, dt.date] = {}
    completed = False
    for offset in range(0, max_pages * page_size, page_size):
        url = (
            f"{_FTS_URL}?q=&forms={forms_param}"
            f"&startdt={start}&enddt={end}&from={offset}"
        )
        payload = json.loads(get(url, headers))
        hits_block = payload.get("hits", {})
        page_hits = hits_block.get("hits", [])
        for event in parse_fts_hits(page_hits):
            cur = by_ticker.get(event.ticker)
            if cur is None or event.delisted_known < cur:
                by_ticker[event.ticker] = event.delisted_known
        total = int(hits_block.get("total", {}).get("value", 0))
        if offset + page_size >= total or not page_hits:
            completed = True
            break
        if http_get is None:
            time.sleep(pause_s)  # real fetch: honour SEC rate limit
    if not completed:
        # Hit the page ceiling before exhausting results — the cache is TRUNCATED,
        # not complete. Surface it loudly so a clipped list isn't mistaken for full.
        _LOG.warning(
            "delisting fetch hit max_pages=%d (%d filings) before exhausting "
            "results for %s..%s — cache is TRUNCATED; raise max_pages or narrow "
            "the date range",
            max_pages, max_pages * page_size, start, end,
        )
    return [
        DelistingEvent(ticker=t, delisted_known=d)
        for t, d in sorted(by_ticker.items())
    ]


def save_delistings_csv(events: list[DelistingEvent], path: Path) -> None:
    """Write events to a 2-column CSV (ticker,delisted_known) — the offline cache."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ticker,delisted_known"]
    lines += [f"{e.ticker},{e.delisted_known.isoformat()}" for e in events]
    path.write_text("\n".join(lines) + "\n")


def load_delistings_csv(path: Path) -> list[DelistingEvent]:
    """Read the cached delisting CSV; missing file -> empty list (offline-safe)."""
    path = Path(path)
    if not path.exists():
        return []
    events: list[DelistingEvent] = []
    for line in path.read_text().splitlines()[1:]:  # skip header
        if not line.strip():
            continue
        ticker, known = line.split(",")
        events.append(
            DelistingEvent(ticker=ticker, delisted_known=dt.date.fromisoformat(known))
        )
    return events
