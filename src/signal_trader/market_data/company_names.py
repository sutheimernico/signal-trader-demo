"""Ticker -> human-friendly company name, from the free SEC ticker list.

The dashboard shows full names (e.g. 'Alphabet' not 'GOOG') so it reads at a
glance. Source: SEC company_tickers.json (free, ~10k US filers, no key). Names
are cleaned (title-cased, legal suffixes like '/UT/' stripped). Cached to JSON so
the API has zero per-request network cost; refreshed by the daily job.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

_SEC_URL = "https://www.sec.gov/files/company_tickers.json"
_SUFFIX_RE = re.compile(r"\s*/[A-Z/]+/\s*$")          # ' /UT/', ' /NEW/'
_LEGAL_RE = re.compile(r"[,/]?\s*(NATIONAL ASSOCIATION|N\.?A\.?|/NEW/?)$", re.I)


def clean_name(title: str) -> str:
    """Make an SEC company title human-friendly."""
    name = _SUFFIX_RE.sub("", str(title)).strip().rstrip(",")
    name = _LEGAL_RE.sub("", name).strip().rstrip(",")
    if name.isupper():  # 'COCA COLA CO' -> 'Coca Cola Co'
        name = name.title()
    # tidy common abbreviations after title-casing
    for a, b in (("Inc.", "Inc"), (" Corp", " Corp"), ("Co.", "Co")):
        name = name.replace(a, b)
    return name or str(title)


def refresh_name_cache(path: Path, identity: str | None = None) -> dict[str, str]:
    """Download the SEC ticker list, clean, cache to `path`, return the map.

    SEC fair-access requires a contactable User-Agent — pass the SEC_IDENTITY
    (Name email), else SEC returns 403.
    """
    ua = identity or "signal-trader research"
    raw = urllib.request.urlopen(
        urllib.request.Request(_SEC_URL, headers={"User-Agent": ua}), timeout=30
    ).read()
    data = json.loads(raw)
    names = {
        str(v["ticker"]).upper(): clean_name(v["title"])
        for v in data.values()
        if v.get("ticker")
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(names, sort_keys=True))
    return names


def load_names(path: Path) -> dict[str, str]:
    """Load the cached ticker->name map, or {} if not yet built."""
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return {}
