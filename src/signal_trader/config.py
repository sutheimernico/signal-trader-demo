"""Repo paths, cache locations, and .env-backed credentials.

No secret is hard-coded; .env is never committed. Paths are absolute and
derived from this file's location so CLI scripts and tests agree.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

DATA_DIR = REPO_ROOT / "data"
PARQUET_DIR = DATA_DIR / "bars"
SQLITE_PATH = DATA_DIR / "signal_trader.sqlite"
CONFIG_DIR = REPO_ROOT / "config"
SP500_SNAPSHOT = CONFIG_DIR / "sp500_snapshot.csv"
# Cached FREE delisting list (SEC Form 25/25-NSE) for the survivorship stress test.
DELISTINGS_CSV = DATA_DIR / "delistings.csv"

DEFAULT_START = "2016-01-01"
DEFAULT_END = "2026-01-01"
TRADING_DAYS_PER_YEAR = 252


def alpaca_credentials() -> tuple[str | None, str | None]:
    """Return (api_key, secret_key) from the environment, or (None, None)."""
    return os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_API_SECRET")


def sec_identity() -> str | None:
    """Return the SEC fair-access identity ('Name email') from the environment.

    edgartools requires this via set_identity; SEC mandates a contactable
    User-Agent and caps requests at ~10/s. None when unset — callers that hit
    the network must raise rather than contact SEC anonymously.
    """
    return os.environ.get("SEC_IDENTITY")
