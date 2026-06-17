# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development — execute each task in its own subagent context, strictly TDD (failing test first, minimal implementation, green, commit), one task at a time, returning only the conclusion. Run the project's `backtest-methodology-reviewer` agent after every task that touches `backtest/`, `strategy/`, `signals/`, or `market_data/`. Never claim a task done before `verification-before-completion` (run the exact commands, paste the real output). All network/SDK calls are faked or mocked in tests — no live calls, ever. Code, identifiers, comments, and commit messages in English.

## Goal

Build the honest measurement harness defined in `PROJECT.md` §5 (Definition of Done): cache S&P-500 daily bars locally, run one transparent momentum baseline through **two** backtest engines (`backtesting.py` event-driven + `vectorbt` vectorized) with flat-per-trade costs and slippage, validate against leakage (shift-test), enforce OOS hold-out and anchored walk-forward, report honest metrics (CAGR, Sharpe, Sortino, Calmar, Max Drawdown, custom PSR) always against a **buy-and-hold benchmark after costs**, add a break-even-cost check, and wire a thin tested Alpaca paper stub. The signature deliverable is the artifact "the same strategy looks better vectorized than event-driven with realistic fills."

No signals, no ML, no dashboard in this phase.

## Architecture

Five-layer split (Spec §4); Phase 1 lights up Data + Sim (Backtest) + a paper stub. Data flows: `scripts/backfill.py` → `PriceProvider` (yfinance) → `BarCache` (Parquet) + `PriceBarStore` (SQLite) → backtest adapters read from cache → `MomentumBaseline` (pure signal function) feeds both `BacktestingPyAdapter` and `VectorbtAdapter` → both pass through the shared `CostModel` → `metrics` + `benchmark` produce the foundation report; `validation` runs shift-test / OOS / walk-forward; `breakeven` sweeps cost levels.

The two backtest engines sit behind a thin adapter seam returning a common `BacktestResult` dataclass, so the same `entries`/`exits` boolean series drive both, and the report can diff them directly.

## Tech Stack

Verified, pinned (June 2026):
- Python ≥ 3.11, env/deps via **uv** (`pyproject.toml` + `uv.lock`).
- `yfinance==1.4.1` — `download(..., auto_adjust=True)` default; multi-ticker access `df[ticker]["Close"]` with `group_by="ticker"`.
- `backtesting==0.6.5` — `Backtest(data, strategy, *, cash, spread, commission, finalize_trades)`; `commission` float = fraction per side; `self.I()`, `crossover()` from `backtesting.lib`; OHLC columns capitalized.
- `vectorbt==1.0.0` — `vbt.Portfolio.from_signals(close, entries, exits, size, fees, slippage, init_cash, freq)`; `fees`/`slippage` decimal fractions; `pf.sharpe_ratio()`, `pf.total_return()`, `pf.stats()`.
- `quantstats-reloaded==0.1.0` — imported as `import quantstats as qs`; `qs.stats.sharpe(returns, rf=0.0, periods=252, annualize=True)`, `sortino(...)`, `calmar(returns)`, `cagr(returns)`, `max_drawdown(prices)`.
- `alpaca-py==0.43.4` — `TradingClient(api_key, secret_key, paper=True)`, `MarketOrderRequest`, `OrderSide`, `TimeInForce`, `client.submit_order(order_data=...)`.
- `pandas`, `numpy`, `pyarrow` (Parquet), `python-dotenv`.
- Lint/format **ruff**; tests **pytest**.

---

## File Structure

Each file, its single responsibility (paths relative to repo root `~/private/signal-trader-demo`):

| File | Responsibility |
|---|---|
| `pyproject.toml` | uv project metadata, pinned deps, ruff + pytest config |
| `src/signal_trader/__init__.py` | package marker |
| `src/signal_trader/config.py` | load `.env`, expose paths + constants (cache dir, DB path, Alpaca keys) |
| `src/signal_trader/market_data/__init__.py` | package marker |
| `src/signal_trader/market_data/universe.py` | deterministic S&P-500 ticker list from bundled CSV; survivorship caveat |
| `src/signal_trader/market_data/provider.py` | `PriceProvider` Protocol + `YFinanceProvider` |
| `src/signal_trader/store/__init__.py` | package marker |
| `src/signal_trader/store/bar_cache.py` | Parquet read/write of bar DataFrames |
| `src/signal_trader/store/price_store.py` | SQLite `price_bars` schema + upsert/read (`PriceBar`) |
| `src/signal_trader/store/cache_service.py` | fetch-through-cache orchestration (provider + parquet + sqlite) |
| `src/signal_trader/backtest/__init__.py` | package marker |
| `src/signal_trader/backtest/costs.py` | `CostModel` (flat per-trade + slippage), shared by both engines |
| `src/signal_trader/backtest/result.py` | `BacktestResult` dataclass (common across engines) |
| `src/signal_trader/backtest/baselines/__init__.py` | package marker |
| `src/signal_trader/backtest/baselines/momentum.py` | pure `momentum_signals(close, lookback)` → entries/exits |
| `src/signal_trader/backtest/engine/__init__.py` | package marker |
| `src/signal_trader/backtest/engine/backtesting_py.py` | `BacktestingPyAdapter` (event-driven) |
| `src/signal_trader/backtest/engine/vectorbt_engine.py` | `VectorbtAdapter` (vectorized) |
| `src/signal_trader/backtest/metrics.py` | quantstats metrics + custom `probabilistic_sharpe_ratio` + `MetricsReport` |
| `src/signal_trader/backtest/benchmark.py` | buy-and-hold equity curve after costs |
| `src/signal_trader/backtest/validation.py` | shift-test, OOS split, anchored walk-forward |
| `src/signal_trader/backtest/breakeven.py` | break-even-cost search (cost where Sharpe = 0) |
| `src/signal_trader/paper/__init__.py` | package marker |
| `src/signal_trader/paper/alpaca/__init__.py` | package marker |
| `src/signal_trader/paper/alpaca/paper_stub.py` | thin tested Alpaca paper order stub |
| `config/sp500_snapshot.csv` | bundled S&P-500 snapshot (ticker,name) — committed |
| `scripts/backfill.py` | CLI: fetch universe → cache |
| `scripts/run_backtest.py` | CLI: foundation report (baseline through both engines + benchmark + diff) |
| `tests/conftest.py` | shared fixtures (synthetic price series, tmp paths) |
| `tests/test_config.py` … `tests/backtest/...` | mirror src, one test module per unit |

---

## Task 0: Tooling & config foundation

**Files:**
- Create: `pyproject.toml`, `src/signal_trader/__init__.py`, `src/signal_trader/config.py`, `tests/test_config.py`, `tests/conftest.py`
- Modify: none

1. Write `tests/test_config.py` with a failing smoke + config test:

```python
from pathlib import Path

import signal_trader
from signal_trader import config


def test_package_importable():
    assert signal_trader.__version__ == "0.1.0"


def test_config_paths_are_absolute_and_under_repo():
    assert config.REPO_ROOT.is_dir()
    assert config.DATA_DIR == config.REPO_ROOT / "data"
    assert config.SQLITE_PATH == config.DATA_DIR / "signal_trader.sqlite"
    assert config.PARQUET_DIR == config.DATA_DIR / "bars"
    assert config.SP500_SNAPSHOT == config.REPO_ROOT / "config" / "sp500_snapshot.csv"
    assert isinstance(config.DATA_DIR, Path)


def test_alpaca_keys_default_to_none_when_env_absent(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    creds = config.alpaca_credentials()
    assert creds == (None, None)


def test_alpaca_keys_read_from_env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key123")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret456")
    assert config.alpaca_credentials() == ("key123", "secret456")
```

2. Run `uv run pytest tests/test_config.py -q` — expect FAIL (`ModuleNotFoundError: signal_trader` / missing `pyproject.toml`).

3. Create `pyproject.toml`:

```toml
[project]
name = "signal-trader-demo"
version = "0.1.0"
description = "Local, free, paper-only backtest harness — honest measurement, no edge promise."
requires-python = ">=3.11"
dependencies = [
    "yfinance==1.4.1",
    "backtesting==0.6.5",
    "vectorbt==1.0.0",
    "quantstats-reloaded==0.1.0",
    "alpaca-py==0.43.4",
    "pandas>=2.2,<3",
    "numpy>=1.26,<3",
    "pyarrow>=16",
    "python-dotenv>=1.0,<2",
]

[dependency-groups]
dev = [
    "pytest>=8.2,<9",
    "ruff>=0.5,<1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/signal_trader"]

[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests", "scripts"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"
```

4. Create `src/signal_trader/__init__.py`:

```python
__version__ = "0.1.0"
```

5. Create `src/signal_trader/config.py`:

```python
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

DEFAULT_START = "2016-01-01"
DEFAULT_END = "2026-01-01"
TRADING_DAYS_PER_YEAR = 252


def alpaca_credentials() -> tuple[str | None, str | None]:
    """Return (api_key, secret_key) from the environment, or (None, None)."""
    return os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
```

6. Create `tests/conftest.py` (shared fixtures used from Task 4 onward):

```python
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def trending_close():
    """Deterministic upward-trending daily close with mild noise (300 bars)."""
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    rng = np.random.default_rng(42)
    drift = np.linspace(0, 0.6, len(idx))
    noise = rng.normal(0, 0.01, len(idx)).cumsum()
    close = 100 * np.exp(drift + noise)
    return pd.Series(close, index=idx, name="Close")


@pytest.fixture
def ohlcv_frame(trending_close):
    """Capitalized OHLCV frame for backtesting.py from a close series."""
    close = trending_close
    return pd.DataFrame(
        {
            "Open": close.shift(1).fillna(close.iloc[0]),
            "High": close * 1.005,
            "Low": close * 0.995,
            "Close": close,
            "Volume": 1_000_000.0,
        }
    )
```

7. Run `uv sync` then `uv run pytest tests/test_config.py -q` — expect PASS (4 passed). Run `uv run ruff check .` — expect clean.

8. Commit: `chore: scaffold uv project, config module, and test harness`

---

## Task 1: S&P-500 universe loader

**Files:**
- Create: `config/sp500_snapshot.csv`, `src/signal_trader/market_data/__init__.py`, `src/signal_trader/market_data/universe.py`, `tests/market_data/__init__.py`, `tests/market_data/test_universe.py`
- Modify: none

1. Write `tests/market_data/test_universe.py`:

```python
import pytest

from signal_trader.market_data import universe


def test_load_universe_returns_sorted_unique_tickers():
    tickers = universe.load_sp500_tickers()
    assert len(tickers) >= 50
    assert tickers == sorted(set(tickers))
    assert all(t.isupper() and t.strip() == t for t in tickers)


def test_load_universe_normalizes_dotted_tickers():
    # Yahoo uses '-' where the index uses '.', e.g. BRK.B -> BRK-B
    tickers = universe.load_sp500_tickers()
    assert "BRK-B" in tickers or "BRK.B" not in tickers


def test_docstring_documents_survivorship_caveat():
    assert "survivorship" in universe.load_sp500_tickers.__doc__.lower()


def test_subset_limits_count():
    assert len(universe.load_sp500_tickers(limit=10)) == 10
```

2. Run `uv run pytest tests/market_data/test_universe.py -q` — expect FAIL (`ModuleNotFoundError`).

3. Create `config/sp500_snapshot.csv` (committed deterministic snapshot, header + representative rows; the real file lists the full constituents as of the snapshot date — full enough to satisfy `>= 50`). Header and first rows:

```csv
ticker,name
AAPL,Apple Inc.
ABBV,AbbVie Inc.
ABT,Abbott Laboratories
ACN,Accenture plc
ADBE,Adobe Inc.
AMD,Advanced Micro Devices
AMGN,Amgen Inc.
AMZN,Amazon.com Inc.
AVGO,Broadcom Inc.
BAC,Bank of America
BRK.B,Berkshire Hathaway
COST,Costco Wholesale
CRM,Salesforce Inc.
CSCO,Cisco Systems
CVX,Chevron Corp.
DIS,Walt Disney Co.
GOOGL,Alphabet Inc. Class A
HD,Home Depot
INTC,Intel Corp.
JNJ,Johnson & Johnson
JPM,JPMorgan Chase
KO,Coca-Cola Co.
LIN,Linde plc
LLY,Eli Lilly
MA,Mastercard Inc.
MCD,McDonald's Corp.
META,Meta Platforms
MRK,Merck & Co.
MSFT,Microsoft Corp.
NFLX,Netflix Inc.
NKE,Nike Inc.
NVDA,NVIDIA Corp.
ORCL,Oracle Corp.
PEP,PepsiCo Inc.
PFE,Pfizer Inc.
PG,Procter & Gamble
TMO,Thermo Fisher
TSLA,Tesla Inc.
TXN,Texas Instruments
UNH,UnitedHealth Group
V,Visa Inc.
WMT,Walmart Inc.
XOM,Exxon Mobil
ADP,Automatic Data Processing
BA,Boeing Co.
C,Citigroup Inc.
CAT,Caterpillar Inc.
GE,General Electric
GS,Goldman Sachs
IBM,IBM Corp.
MMM,3M Co.
PM,Philip Morris Intl
QCOM,Qualcomm Inc.
SBUX,Starbucks Corp.
T,AT&T Inc.
UPS,United Parcel Service
VZ,Verizon Communications
WFC,Wells Fargo
```

4. Create `src/signal_trader/market_data/__init__.py` (empty) and `tests/market_data/__init__.py` (empty).

5. Create `src/signal_trader/market_data/universe.py`:

```python
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
```

6. Run `uv run pytest tests/market_data/test_universe.py -q` — expect PASS (4 passed).

7. Commit: `feat(market_data): add deterministic S&P-500 universe loader`

---

## Task 2: PriceProvider protocol + yfinance provider

**Files:**
- Create: `src/signal_trader/market_data/provider.py`, `tests/market_data/test_provider.py`
- Modify: none

1. Write `tests/market_data/test_provider.py` (yfinance is mocked — no live call):

```python
from unittest.mock import patch

import pandas as pd
import pytest

from signal_trader.market_data.provider import PriceProvider, YFinanceProvider


def _fake_yf_multiindex(tickers):
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    frames = {}
    for i, t in enumerate(tickers):
        base = 100 + i
        frames[(t, "Open")] = [base, base + 1, base + 2]
        frames[(t, "High")] = [base + 1, base + 2, base + 3]
        frames[(t, "Low")] = [base - 1, base, base + 1]
        frames[(t, "Close")] = [base + 0.5, base + 1.5, base + 2.5]
        frames[(t, "Volume")] = [1e6, 1.1e6, 1.2e6]
    cols = pd.MultiIndex.from_tuples(frames.keys(), names=["Ticker", "Price"])
    return pd.DataFrame(frames, index=idx).reindex(columns=cols)


def test_yfinance_provider_satisfies_protocol():
    assert isinstance(YFinanceProvider(), PriceProvider)


def test_fetch_returns_long_frame_with_expected_columns():
    with patch("signal_trader.market_data.provider.yf.download") as dl:
        dl.return_value = _fake_yf_multiindex(["AAPL", "MSFT"])
        out = YFinanceProvider().fetch(["AAPL", "MSFT"], "2020-01-01", "2020-01-06")
    assert list(out.columns) == [
        "ticker", "date", "open", "high", "low", "close", "volume"
    ]
    assert set(out["ticker"]) == {"AAPL", "MSFT"}
    assert len(out) == 6
    assert pd.api.types.is_datetime64_any_dtype(out["date"])


def test_fetch_passes_auto_adjust_true_and_group_by_ticker():
    with patch("signal_trader.market_data.provider.yf.download") as dl:
        dl.return_value = _fake_yf_multiindex(["AAPL"])
        YFinanceProvider().fetch(["AAPL"], "2020-01-01", "2020-01-06")
    _, kwargs = dl.call_args
    assert kwargs["auto_adjust"] is True
    assert kwargs["group_by"] == "ticker"
    assert kwargs["progress"] is False


def test_fetch_empty_tickers_raises():
    with pytest.raises(ValueError):
        YFinanceProvider().fetch([], "2020-01-01", "2020-01-06")
```

2. Run `uv run pytest tests/market_data/test_provider.py -q` — expect FAIL (`ModuleNotFoundError`).

3. Create `src/signal_trader/market_data/provider.py`:

```python
"""Market-data provider seam.

A thin `PriceProvider` Protocol decouples the cache from the vendor.
yfinance is the v1 implementation; Tiingo can drop in later behind the
same interface. CAVEAT: auto_adjust=True returns back-adjusted OHLC, i.e.
values restated for later splits/dividends — a subtle lookahead. We keep
it (free, simple) and document it; downstream code must not pretend these
were the prices known on the bar's date.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd
import yfinance as yf

_LONG_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]


@runtime_checkable
class PriceProvider(Protocol):
    def fetch(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        """Return long-form daily bars with columns: ticker, date, open,
        high, low, close, volume."""
        ...


class YFinanceProvider:
    """yfinance-backed provider returning normalized long-form bars."""

    def fetch(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        if not tickers:
            raise ValueError("tickers must not be empty")
        raw = yf.download(
            tickers,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
        return self._to_long(raw, tickers)

    @staticmethod
    def _to_long(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame(columns=_LONG_COLUMNS)
        rename = {"Open": "open", "High": "high", "Low": "low",
                  "Close": "close", "Volume": "volume"}
        parts: list[pd.DataFrame] = []
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(0):
                continue
            sub = raw[ticker].rename(columns=rename).dropna(how="all")
            sub = sub.reset_index().rename(columns={"Date": "date", "index": "date"})
            sub.insert(0, "ticker", ticker)
            parts.append(sub[_LONG_COLUMNS])
        if not parts:
            return pd.DataFrame(columns=_LONG_COLUMNS)
        out = pd.concat(parts, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"])
        return out.sort_values(["ticker", "date"]).reset_index(drop=True)
```

4. Run `uv run pytest tests/market_data/test_provider.py -q` — expect PASS (4 passed).

5. Run `backtest-methodology-reviewer` against `src/signal_trader/market_data/` (focus: the auto_adjust lookahead caveat must be documented — it is). Commit: `feat(market_data): add PriceProvider protocol and yfinance provider`

---

## Task 3: Parquet cache + SQLite store + fetch-through-cache

**Files:**
- Create: `src/signal_trader/store/__init__.py`, `src/signal_trader/store/bar_cache.py`, `src/signal_trader/store/price_store.py`, `src/signal_trader/store/cache_service.py`, `tests/store/__init__.py`, `tests/store/test_bar_cache.py`, `tests/store/test_price_store.py`, `tests/store/test_cache_service.py`
- Modify: none

1. Write `tests/store/test_price_store.py`:

```python
import pandas as pd

from signal_trader.store.price_store import PriceBarStore


def _bars(ticker="AAPL"):
    return pd.DataFrame(
        {
            "ticker": [ticker, ticker],
            "date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1e6, 1.1e6],
        }
    )


def test_upsert_then_read_roundtrip(tmp_path):
    store = PriceBarStore(tmp_path / "t.sqlite")
    store.upsert_bars(_bars())
    out = store.read_bars(["AAPL"], "2020-01-01", "2020-01-10")
    assert len(out) == 2
    assert list(out.columns) == [
        "ticker", "date", "open", "high", "low", "close", "volume"
    ]


def test_upsert_is_idempotent_on_ticker_date(tmp_path):
    store = PriceBarStore(tmp_path / "t.sqlite")
    store.upsert_bars(_bars())
    store.upsert_bars(_bars())  # same primary key -> replace, not duplicate
    assert len(store.read_bars(["AAPL"], "2020-01-01", "2020-01-10")) == 2


def test_cached_tickers_reports_coverage(tmp_path):
    store = PriceBarStore(tmp_path / "t.sqlite")
    store.upsert_bars(_bars())
    assert store.cached_tickers() == {"AAPL"}
```

2. Run `uv run pytest tests/store/test_price_store.py -q` — expect FAIL.

3. Create `src/signal_trader/store/__init__.py` (empty), `tests/store/__init__.py` (empty), and `src/signal_trader/store/price_store.py`:

```python
"""SQLite store for daily price bars (the structured cache).

One table, primary key (ticker, date) so re-fetches upsert cleanly.
`fetched_at` records when the row entered the cache (data-lag visibility).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_bars (
    ticker     TEXT    NOT NULL,
    date       TEXT    NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    source     TEXT    NOT NULL DEFAULT 'yfinance',
    fetched_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, date)
);
"""


class PriceBarStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def upsert_bars(self, bars: pd.DataFrame, source: str = "yfinance") -> None:
        if bars.empty:
            return
        rows = bars[_COLUMNS].copy()
        rows["date"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d")
        records = [
            (*tuple(r), source)
            for r in rows.itertuples(index=False, name=None)
        ]
        with self._connect() as con:
            con.executemany(
                "INSERT OR REPLACE INTO price_bars "
                "(ticker, date, open, high, low, close, volume, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                records,
            )

    def read_bars(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        placeholders = ",".join("?" for _ in tickers)
        query = (
            f"SELECT {', '.join(_COLUMNS)} FROM price_bars "
            f"WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ? "
            "ORDER BY ticker, date"
        )
        with self._connect() as con:
            out = pd.read_sql_query(query, con, params=[*tickers, start, end])
        out["date"] = pd.to_datetime(out["date"])
        return out

    def cached_tickers(self) -> set[str]:
        with self._connect() as con:
            rows = con.execute("SELECT DISTINCT ticker FROM price_bars").fetchall()
        return {r[0] for r in rows}
```

4. Run `uv run pytest tests/store/test_price_store.py -q` — expect PASS (3 passed).

5. Write `tests/store/test_bar_cache.py`:

```python
import pandas as pd

from signal_trader.store.bar_cache import BarCache


def _bars(ticker="AAPL"):
    return pd.DataFrame(
        {
            "ticker": [ticker],
            "date": pd.to_datetime(["2020-01-02"]),
            "open": [100.0], "high": [101.0], "low": [99.0],
            "close": [100.5], "volume": [1e6],
        }
    )


def test_write_then_read_parquet_roundtrip(tmp_path):
    cache = BarCache(tmp_path)
    cache.write("AAPL", _bars())
    out = cache.read("AAPL")
    pd.testing.assert_frame_equal(out.reset_index(drop=True), _bars())


def test_has_reports_presence(tmp_path):
    cache = BarCache(tmp_path)
    assert cache.has("AAPL") is False
    cache.write("AAPL", _bars())
    assert cache.has("AAPL") is True
```

6. Run `uv run pytest tests/store/test_bar_cache.py -q` — expect FAIL.

7. Create `src/signal_trader/store/bar_cache.py`:

```python
"""Per-ticker Parquet cache for raw bars (the columnar cache).

One file per ticker keeps re-fetches cheap and the working set small.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


class BarCache:
    def __init__(self, parquet_dir: Path):
        self.parquet_dir = Path(parquet_dir)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, ticker: str) -> Path:
        return self.parquet_dir / f"{ticker}.parquet"

    def has(self, ticker: str) -> bool:
        return self._path(ticker).exists()

    def write(self, ticker: str, bars: pd.DataFrame) -> None:
        bars.to_parquet(self._path(ticker), index=False)

    def read(self, ticker: str) -> pd.DataFrame:
        return pd.read_parquet(self._path(ticker))
```

8. Run `uv run pytest tests/store/test_bar_cache.py -q` — expect PASS (2 passed).

9. Write `tests/store/test_cache_service.py` (provider faked — no live call):

```python
import pandas as pd

from signal_trader.store.cache_service import CacheService


class FakeProvider:
    def __init__(self):
        self.calls = []

    def fetch(self, tickers, start, end):
        self.calls.append(list(tickers))
        frames = []
        for t in tickers:
            frames.append(pd.DataFrame({
                "ticker": [t], "date": pd.to_datetime(["2020-01-02"]),
                "open": [1.0], "high": [1.0], "low": [1.0],
                "close": [1.0], "volume": [1.0],
            }))
        return pd.concat(frames, ignore_index=True)


def test_backfill_fetches_missing_only(tmp_path):
    provider = FakeProvider()
    svc = CacheService(provider, tmp_path / "bars", tmp_path / "t.sqlite")
    svc.backfill(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    assert sorted(provider.calls[0]) == ["AAPL", "MSFT"]

    svc.backfill(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")  # already cached
    assert len(provider.calls) == 1  # no second fetch


def test_load_close_matrix_returns_wide_frame(tmp_path):
    provider = FakeProvider()
    svc = CacheService(provider, tmp_path / "bars", tmp_path / "t.sqlite")
    svc.backfill(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    close = svc.load_close_matrix(["AAPL", "MSFT"], "2020-01-01", "2020-01-10")
    assert list(close.columns) == ["AAPL", "MSFT"]
    assert close.index.name == "date"
```

10. Run `uv run pytest tests/store/test_cache_service.py -q` — expect FAIL.

11. Create `src/signal_trader/store/cache_service.py`:

```python
"""Fetch-through-cache: pull once from the provider, serve from cache after.

Backtests read from this, never from the live provider — reproducible and
rate-limit-free (Spec §5.1). A ticker is 'cached' if its Parquet file exists.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from signal_trader.market_data.provider import PriceProvider
from signal_trader.store.bar_cache import BarCache
from signal_trader.store.price_store import PriceBarStore


class CacheService:
    def __init__(self, provider: PriceProvider, parquet_dir: Path, db_path: Path):
        self.provider = provider
        self.cache = BarCache(parquet_dir)
        self.store = PriceBarStore(db_path)

    def backfill(self, tickers: list[str], start: str, end: str) -> None:
        missing = [t for t in tickers if not self.cache.has(t)]
        if not missing:
            return
        bars = self.provider.fetch(missing, start, end)
        if bars.empty:
            return
        self.store.upsert_bars(bars)
        for ticker, group in bars.groupby("ticker"):
            self.cache.write(str(ticker), group.reset_index(drop=True))

    def load_close_matrix(
        self, tickers: list[str], start: str, end: str
    ) -> pd.DataFrame:
        bars = self.store.read_bars(tickers, start, end)
        wide = bars.pivot(index="date", columns="ticker", values="close")
        wide.index.name = "date"
        return wide[[t for t in tickers if t in wide.columns]]
```

12. Run `uv run pytest tests/store/ -q` — expect PASS (8 passed).

13. Commit: `feat(store): add Parquet cache, SQLite store, and fetch-through-cache`

---

## Task 4: Cost model (flat per-trade + slippage)

**Files:**
- Create: `src/signal_trader/backtest/__init__.py`, `src/signal_trader/backtest/costs.py`, `tests/backtest/__init__.py`, `tests/backtest/test_costs.py`
- Modify: none

1. Write `tests/backtest/test_costs.py`:

```python
import pytest

from signal_trader.backtest.costs import CostModel


def test_commission_fraction_default():
    cm = CostModel(commission_per_trade=0.001, slippage=0.0005)
    assert cm.commission_per_trade == 0.001
    assert cm.slippage == 0.0005


def test_round_trip_fraction_is_two_legs_of_commission_plus_slippage():
    cm = CostModel(commission_per_trade=0.001, slippage=0.0005)
    # entry + exit: 2 * (commission + slippage)
    assert cm.round_trip_fraction() == pytest.approx(2 * (0.001 + 0.0005))


def test_apply_slippage_buy_raises_price_sell_lowers_price():
    cm = CostModel(commission_per_trade=0.0, slippage=0.01)
    assert cm.fill_price(100.0, side="buy") == pytest.approx(101.0)
    assert cm.fill_price(100.0, side="sell") == pytest.approx(99.0)


def test_negative_costs_rejected():
    with pytest.raises(ValueError):
        CostModel(commission_per_trade=-0.001, slippage=0.0)
    with pytest.raises(ValueError):
        CostModel(commission_per_trade=0.0, slippage=-0.1)


def test_invalid_side_rejected():
    cm = CostModel(commission_per_trade=0.0, slippage=0.01)
    with pytest.raises(ValueError):
        cm.fill_price(100.0, side="hold")
```

2. Run `uv run pytest tests/backtest/test_costs.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/__init__.py` (empty), `tests/backtest/__init__.py` (empty), and `src/signal_trader/backtest/costs.py`:

```python
"""Shared cost model: flat per-trade commission + slippage, as fractions.

One tested unit feeds BOTH engines and the benchmark, so 'after costs'
means the same thing everywhere (Acceptance criterion §8.6). Both values
are per-side fractions of notional. backtesting.py's `commission` is also a
per-side fraction; vectorbt's `fees`/`slippage` are per-side fractions too,
so this maps directly onto both engines.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_per_trade: float
    slippage: float

    def __post_init__(self) -> None:
        if self.commission_per_trade < 0:
            raise ValueError("commission_per_trade must be >= 0")
        if self.slippage < 0:
            raise ValueError("slippage must be >= 0")

    def round_trip_fraction(self) -> float:
        """Fraction lost on a full buy+sell round trip (both legs)."""
        return 2 * (self.commission_per_trade + self.slippage)

    def fill_price(self, mid_price: float, side: str) -> float:
        """Slippage-adjusted fill: buys fill higher, sells lower."""
        if side == "buy":
            return mid_price * (1 + self.slippage)
        if side == "sell":
            return mid_price * (1 - self.slippage)
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
```

4. Run `uv run pytest tests/backtest/test_costs.py -q` — expect PASS (5 passed).

5. Commit: `feat(backtest): add shared flat-per-trade + slippage cost model`

---

## Task 5: Momentum baseline (pure signal function)

**Files:**
- Create: `src/signal_trader/backtest/baselines/__init__.py`, `src/signal_trader/backtest/baselines/momentum.py`, `tests/backtest/baselines/__init__.py`, `tests/backtest/baselines/test_momentum.py`
- Modify: none

1. Write `tests/backtest/baselines/test_momentum.py`:

```python
import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.baselines.momentum import momentum_signals


def test_entries_and_exits_are_aligned_boolean_series():
    close = pd.Series(np.linspace(100, 120, 60),
                      index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries, exits = momentum_signals(close, lookback=20)
    assert entries.dtype == bool and exits.dtype == bool
    assert entries.index.equals(close.index)
    assert exits.index.equals(close.index)


def test_uptrend_enters_and_downtrend_exits():
    up = pd.Series(np.linspace(100, 200, 60),
                   index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries, exits = momentum_signals(up, lookback=20)
    assert entries.iloc[30:].any()
    down = pd.Series(np.linspace(200, 100, 60),
                     index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries_d, exits_d = momentum_signals(down, lookback=20)
    assert exits_d.iloc[30:].any()


def test_no_signal_during_warmup_window():
    close = pd.Series(np.linspace(100, 120, 60),
                      index=pd.date_range("2020-01-01", periods=60, freq="B"))
    entries, exits = momentum_signals(close, lookback=20)
    # SMA undefined for the first `lookback` bars -> no entries there
    assert not entries.iloc[:20].any()


def test_signals_are_shifted_one_bar_to_prevent_lookahead():
    # A close-based signal must act on the NEXT bar, never the same close.
    close = pd.Series(
        [100, 100, 100, 100, 105, 105, 105, 105, 105, 105],
        index=pd.date_range("2020-01-01", periods=10, freq="B"),
        dtype=float,
    )
    entries, _ = momentum_signals(close, lookback=3)
    # the crossover happens on the close at position 4; the entry signal
    # must appear no earlier than position 5 (acted on next bar).
    first_entry = entries.idxmax() if entries.any() else None
    assert first_entry is None or entries.index.get_loc(first_entry) >= 5


def test_lookback_must_be_positive():
    close = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        momentum_signals(close, lookback=0)
```

2. Run `uv run pytest tests/backtest/baselines/test_momentum.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/baselines/__init__.py` (empty), `tests/backtest/baselines/__init__.py` (empty), and `src/signal_trader/backtest/baselines/momentum.py`:

```python
"""Pure momentum baseline signal — harness validation only, not an edge.

Rule: long while close > SMA(lookback), flat otherwise. The signal is
computed from each bar's close, then SHIFTED one bar so a position taken
on the signal trades on the NEXT bar — this is the leakage guard the
shift-test later stresses (signal t -> position t+1 -> return t+2).
"""
from __future__ import annotations

import pandas as pd


def momentum_signals(
    close: pd.Series, lookback: int = 50
) -> tuple[pd.Series, pd.Series]:
    """Return (entries, exits) boolean Series aligned to `close`.

    entries: cross above SMA(lookback); exits: cross below. Both shifted by
    one bar to avoid same-bar lookahead.
    """
    if lookback <= 0:
        raise ValueError("lookback must be positive")
    sma = close.rolling(lookback).mean()
    above = close > sma
    raw_entries = above & ~above.shift(1, fill_value=False)
    raw_exits = ~above & above.shift(1, fill_value=False)
    entries = raw_entries.shift(1, fill_value=False).fillna(False).astype(bool)
    exits = raw_exits.shift(1, fill_value=False).fillna(False).astype(bool)
    entries.index = close.index
    exits.index = close.index
    return entries, exits
```

4. Run `uv run pytest tests/backtest/baselines/test_momentum.py -q` — expect PASS (5 passed).

5. Run `backtest-methodology-reviewer` against `src/signal_trader/backtest/baselines/` (focus: the one-bar shift is the leakage guard — confirm it is present and tested). Commit: `feat(baselines): add pure momentum signal with one-bar lookahead guard`

---

## Task 6: backtesting.py adapter (event-driven, with costs)

**Files:**
- Create: `src/signal_trader/backtest/result.py`, `src/signal_trader/backtest/engine/__init__.py`, `src/signal_trader/backtest/engine/backtesting_py.py`, `tests/backtest/engine/__init__.py`, `tests/backtest/engine/test_backtesting_py.py`
- Modify: none

1. Write `tests/backtest/engine/test_backtesting_py.py` (uses `ohlcv_frame` from conftest; runs the real fast in-process engine — no network):

```python
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.engine.backtesting_py import BacktestingPyAdapter
from signal_trader.backtest.result import BacktestResult


def test_run_returns_backtest_result(ohlcv_frame):
    adapter = BacktestingPyAdapter(CostModel(commission_per_trade=0.001, slippage=0.0))
    result = adapter.run(ohlcv_frame, lookback=20)
    assert isinstance(result, BacktestResult)
    assert result.engine == "backtesting.py"
    assert isinstance(result.equity_curve, pd.Series)
    assert len(result.equity_curve) > 0
    assert result.n_trades >= 0


def test_costs_reduce_final_equity(ohlcv_frame):
    free = BacktestingPyAdapter(
        CostModel(commission_per_trade=0.0, slippage=0.0)
    ).run(ohlcv_frame, lookback=20)
    costly = BacktestingPyAdapter(
        CostModel(commission_per_trade=0.02, slippage=0.01)
    ).run(ohlcv_frame, lookback=20)
    if free.n_trades > 0:
        assert costly.equity_curve.iloc[-1] <= free.equity_curve.iloc[-1]


def test_equity_curve_indexed_by_date(ohlcv_frame):
    result = BacktestingPyAdapter(
        CostModel(commission_per_trade=0.001, slippage=0.0)
    ).run(ohlcv_frame, lookback=20)
    assert isinstance(result.equity_curve.index, pd.DatetimeIndex)
```

2. Run `uv run pytest tests/backtest/engine/test_backtesting_py.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/result.py`:

```python
"""Common result shape so both engines return the same thing.

`equity_curve` is the post-cost account value indexed by date; downstream
metrics derive returns from it. This is the seam that lets the report diff
event-driven vs vectorized on equal footing.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class BacktestResult:
    engine: str
    equity_curve: pd.Series
    n_trades: int

    def returns(self) -> pd.Series:
        """Periodic returns derived from the equity curve."""
        return self.equity_curve.pct_change().dropna()
```

4. Create `src/signal_trader/backtest/engine/__init__.py` (empty), `tests/backtest/engine/__init__.py` (empty), and `src/signal_trader/backtest/engine/backtesting_py.py`:

```python
"""Event-driven adapter over backtesting.py 0.6.5.

Same momentum signal as the vectorbt adapter, but with realistic next-bar
fills, so the report can show event-driven trailing vectorized. Costs:
backtesting.py's `commission` (per-side fraction) carries our commission;
slippage is folded into `spread` (a per-trade relative bid-ask cost).
"""
from __future__ import annotations

import pandas as pd
from backtesting import Backtest, Strategy

from signal_trader.backtest.baselines.momentum import momentum_signals
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.result import BacktestResult

_INIT_CASH = 10_000


def _make_strategy(lookback: int) -> type[Strategy]:
    class _Momentum(Strategy):
        def init(self):
            close = pd.Series(self.data.Close, index=self.data.index)
            entries, exits = momentum_signals(close, lookback=lookback)
            self.entries = self.I(lambda: entries.to_numpy(), name="entries")
            self.exits = self.I(lambda: exits.to_numpy(), name="exits")

        def next(self):
            if self.entries[-1] and not self.position:
                self.buy()
            elif self.exits[-1] and self.position:
                self.position.close()

    return _Momentum


class BacktestingPyAdapter:
    def __init__(self, cost_model: CostModel):
        self.cost_model = cost_model

    def run(self, ohlcv: pd.DataFrame, lookback: int = 50) -> BacktestResult:
        bt = Backtest(
            ohlcv,
            _make_strategy(lookback),
            cash=_INIT_CASH,
            commission=self.cost_model.commission_per_trade,
            spread=self.cost_model.slippage,
            finalize_trades=True,
        )
        stats = bt.run()
        equity = stats["_equity_curve"]["Equity"]
        equity.index = pd.DatetimeIndex(ohlcv.index)
        return BacktestResult(
            engine="backtesting.py",
            equity_curve=equity,
            n_trades=int(stats["# Trades"]),
        )
```

5. Run `uv run pytest tests/backtest/engine/test_backtesting_py.py -q` — expect PASS (3 passed).

6. Run `backtest-methodology-reviewer` against `src/signal_trader/backtest/engine/backtesting_py.py` (focus: next-bar fill, costs charged, no same-bar trade). Commit: `feat(engine): add event-driven backtesting.py adapter with costs`

---

## Task 7: vectorbt adapter (same signals)

**Files:**
- Create: `src/signal_trader/backtest/engine/vectorbt_engine.py`, `tests/backtest/engine/test_vectorbt_engine.py`
- Modify: none

1. Write `tests/backtest/engine/test_vectorbt_engine.py`:

```python
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.engine.vectorbt_engine import VectorbtAdapter
from signal_trader.backtest.result import BacktestResult


def test_run_returns_backtest_result(trending_close):
    result = VectorbtAdapter(
        CostModel(commission_per_trade=0.001, slippage=0.0005)
    ).run(trending_close, lookback=20)
    assert isinstance(result, BacktestResult)
    assert result.engine == "vectorbt"
    assert isinstance(result.equity_curve, pd.Series)
    assert len(result.equity_curve) == len(trending_close)


def test_costs_reduce_final_equity(trending_close):
    free = VectorbtAdapter(
        CostModel(commission_per_trade=0.0, slippage=0.0)
    ).run(trending_close, lookback=20)
    costly = VectorbtAdapter(
        CostModel(commission_per_trade=0.02, slippage=0.01)
    ).run(trending_close, lookback=20)
    if free.n_trades > 0:
        assert costly.equity_curve.iloc[-1] <= free.equity_curve.iloc[-1]


def test_equity_curve_indexed_by_date(trending_close):
    result = VectorbtAdapter(
        CostModel(commission_per_trade=0.001, slippage=0.0)
    ).run(trending_close, lookback=20)
    assert isinstance(result.equity_curve.index, pd.DatetimeIndex)
```

2. Run `uv run pytest tests/backtest/engine/test_vectorbt_engine.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/engine/vectorbt_engine.py`:

```python
"""Vectorized adapter over vectorbt 1.0.0.

Same momentum entries/exits as the event-driven adapter. fees/slippage are
per-side fractions (map directly from CostModel). freq='1D' so vectorbt can
annualize. The equity curve here is `pf.value()` — note it does NOT model
next-bar-open fills, which is exactly why the report shows it looking
better than the event-driven run on identical signals.
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt

from signal_trader.backtest.baselines.momentum import momentum_signals
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.result import BacktestResult

_INIT_CASH = 10_000


class VectorbtAdapter:
    def __init__(self, cost_model: CostModel):
        self.cost_model = cost_model

    def run(self, close: pd.Series, lookback: int = 50) -> BacktestResult:
        entries, exits = momentum_signals(close, lookback=lookback)
        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            init_cash=_INIT_CASH,
            fees=self.cost_model.commission_per_trade,
            slippage=self.cost_model.slippage,
            freq="1D",
        )
        equity = pf.value()
        equity.index = pd.DatetimeIndex(close.index)
        return BacktestResult(
            engine="vectorbt",
            equity_curve=equity,
            n_trades=int(pf.trades.count()),
        )
```

4. Run `uv run pytest tests/backtest/engine/test_vectorbt_engine.py -q` — expect PASS (3 passed).

5. Run `backtest-methodology-reviewer` against both engine files (focus: same signal source, costs charged in both, the realism gap is intentional and documented). Commit: `feat(engine): add vectorbt adapter sharing the momentum signal`

---

## Task 8: Metrics (quantstats + custom PSR) + after-cost benchmark

**Files:**
- Create: `src/signal_trader/backtest/metrics.py`, `src/signal_trader/backtest/benchmark.py`, `tests/backtest/test_metrics.py`, `tests/backtest/test_benchmark.py`
- Modify: none

1. Write `tests/backtest/test_metrics.py`:

```python
import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.metrics import (
    MetricsReport,
    compute_metrics,
    probabilistic_sharpe_ratio,
)


def _returns(mean=0.0008, vol=0.01, n=756, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(rng.normal(mean, vol, n), index=idx)


def test_compute_metrics_returns_report_with_all_fields():
    rep = compute_metrics(_returns())
    assert isinstance(rep, MetricsReport)
    for field in ("cagr", "sharpe", "sortino", "calmar", "max_drawdown", "psr"):
        assert isinstance(getattr(rep, field), float)


def test_psr_in_unit_interval():
    psr = probabilistic_sharpe_ratio(_returns(), benchmark_sharpe=0.0)
    assert 0.0 <= psr <= 1.0


def test_psr_rises_with_more_evidence_of_positive_sharpe():
    strong = _returns(mean=0.0015, vol=0.008, n=1500, seed=2)
    weak = _returns(mean=0.0002, vol=0.02, n=120, seed=3)
    assert (
        probabilistic_sharpe_ratio(strong, 0.0)
        > probabilistic_sharpe_ratio(weak, 0.0)
    )


def test_psr_against_higher_benchmark_is_lower():
    r = _returns()
    assert (
        probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0)
        >= probabilistic_sharpe_ratio(r, benchmark_sharpe=1.0)
    )


def test_psr_rejects_too_few_observations():
    with pytest.raises(ValueError):
        probabilistic_sharpe_ratio(pd.Series([0.01]), 0.0)
```

2. Run `uv run pytest tests/backtest/test_metrics.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/metrics.py`:

```python
"""Honest metrics: quantstats headline ratios + a self-contained PSR.

Never Sharpe alone (Acceptance §8.6): CAGR, Sharpe, Sortino, Calmar, Max
Drawdown together. PSR (Bailey & Lopez de Prado) reports the probability
that the observed Sharpe exceeds a benchmark Sharpe, correcting for sample
length, skew, and kurtosis — the divergence between Sharpe and PSR is the
information.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import quantstats as qs

from signal_trader.config import TRADING_DAYS_PER_YEAR


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probabilistic_sharpe_ratio(
    returns: pd.Series, benchmark_sharpe: float = 0.0
) -> float:
    """Probability that the true (non-annualized) Sharpe exceeds the
    benchmark, with skew/kurtosis correction.

    Sharpe and benchmark_sharpe are per-period (not annualized) here.
    """
    r = returns.dropna().to_numpy()
    n = r.size
    if n < 2:
        raise ValueError("need at least 2 observations for PSR")
    std = r.std(ddof=1)
    if std == 0:
        return 1.0 if r.mean() > benchmark_sharpe else 0.0
    sr = r.mean() / std
    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurtosis()) + 3.0  # pandas gives excess kurtosis
    numerator = (sr - benchmark_sharpe) * math.sqrt(n - 1)
    denominator = math.sqrt(1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr**2)
    return _normal_cdf(numerator / denominator)


@dataclass
class MetricsReport:
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    psr: float


def compute_metrics(
    returns: pd.Series, periods: int = TRADING_DAYS_PER_YEAR
) -> MetricsReport:
    """Compute the honest metric set from a periodic return series."""
    r = returns.dropna()
    return MetricsReport(
        cagr=float(qs.stats.cagr(r, periods=periods)),
        sharpe=float(qs.stats.sharpe(r, rf=0.0, periods=periods, annualize=True)),
        sortino=float(qs.stats.sortino(r, rf=0.0, periods=periods, annualize=True)),
        calmar=float(qs.stats.calmar(r)),
        max_drawdown=float(qs.stats.max_drawdown((1 + r).cumprod())),
        psr=probabilistic_sharpe_ratio(r, benchmark_sharpe=0.0),
    )
```

4. Run `uv run pytest tests/backtest/test_metrics.py -q` — expect PASS (5 passed).

5. Write `tests/backtest/test_benchmark.py`:

```python
import numpy as np
import pandas as pd

from signal_trader.backtest.benchmark import buy_and_hold_equity
from signal_trader.backtest.costs import CostModel


def test_buy_and_hold_tracks_price_minus_entry_costs():
    close = pd.Series(
        [100.0, 110.0, 120.0],
        index=pd.date_range("2020-01-01", periods=3, freq="B"),
    )
    eq = buy_and_hold_equity(close, CostModel(0.0, 0.0), init_cash=1000.0)
    # no costs: 10 shares * price
    assert eq.iloc[0] == 1000.0
    assert eq.iloc[-1] == 1200.0


def test_costs_reduce_benchmark_equity():
    close = pd.Series(
        np.linspace(100, 150, 50),
        index=pd.date_range("2020-01-01", periods=50, freq="B"),
    )
    free = buy_and_hold_equity(close, CostModel(0.0, 0.0))
    costly = buy_and_hold_equity(close, CostModel(0.005, 0.002))
    assert costly.iloc[-1] < free.iloc[-1]


def test_equity_aligned_to_price_index():
    close = pd.Series(
        np.linspace(100, 150, 50),
        index=pd.date_range("2020-01-01", periods=50, freq="B"),
    )
    eq = buy_and_hold_equity(close, CostModel(0.001, 0.0))
    assert eq.index.equals(close.index)
```

6. Run `uv run pytest tests/backtest/test_benchmark.py -q` — expect FAIL.

7. Create `src/signal_trader/backtest/benchmark.py`:

```python
"""Buy-and-hold benchmark, charged the SAME costs as the strategy.

Acceptance §8.6: performance is always measured against a benchmark after
costs. We buy once at the first bar (paying entry commission + slippage)
and hold; equity is share count times close thereafter.
"""
from __future__ import annotations

import pandas as pd

from signal_trader.backtest.costs import CostModel


def buy_and_hold_equity(
    close: pd.Series, cost_model: CostModel, init_cash: float = 10_000.0
) -> pd.Series:
    """Post-cost equity curve of buying the asset on bar 0 and holding."""
    entry_price = cost_model.fill_price(float(close.iloc[0]), side="buy")
    commission_cash = init_cash * cost_model.commission_per_trade
    investable = init_cash - commission_cash
    shares = investable / entry_price
    equity = shares * close
    equity.index = close.index
    return equity
```

8. Run `uv run pytest tests/backtest/test_benchmark.py -q` — expect PASS (3 passed).

9. Run `backtest-methodology-reviewer` against `metrics.py` + `benchmark.py` (focus: benchmark charged the same costs, PSR present, no Sharpe-only path). Commit: `feat(backtest): add quantstats metrics, custom PSR, and after-cost benchmark`

---

## Task 9: Validation harness (shift-test, OOS split, anchored walk-forward)

**Files:**
- Create: `src/signal_trader/backtest/validation.py`, `tests/backtest/test_validation.py`
- Modify: none

1. Write `tests/backtest/test_validation.py`:

```python
import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.validation import (
    anchored_walk_forward,
    oos_split,
    shift_test,
)


def _close(n=400, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(100 * np.exp(rng.normal(0.0004, 0.01, n).cumsum()), index=idx)


def test_oos_split_is_chronological_and_disjoint():
    close = _close()
    is_, oos = oos_split(close, oos_fraction=0.3)
    assert is_.index.max() < oos.index.min()
    assert len(is_) + len(oos) == len(close)
    assert round(len(oos) / len(close), 1) == 0.3


def test_shift_test_returns_both_sharpes_and_a_collapse_flag():
    close = _close()

    def run(series):
        # toy metric that depends on a one-bar-ahead relationship
        return float(series.pct_change().mean())

    res = shift_test(close, run, lag=1)
    assert set(res) == {"baseline", "shifted", "collapsed"}
    assert isinstance(res["collapsed"], bool)


def test_shift_test_flags_leakage_when_shifting_destroys_performance():
    close = _close()

    # leaky metric: peeks at NEXT bar's return (perfect foresight)
    def leaky(series):
        return float(series.pct_change().shift(-1).fillna(0).abs().mean())

    res = shift_test(close, leaky, lag=1)
    # shifting all inputs by one bar must change the leaky result
    assert res["baseline"] != res["shifted"]


def test_anchored_walk_forward_windows_expand_and_are_ordered():
    close = _close(n=300)
    windows = anchored_walk_forward(close, n_splits=3, test_size=50)
    assert len(windows) == 3
    prev_train_end = None
    for train, test in windows:
        assert train.index.max() < test.index.min()
        if prev_train_end is not None:
            assert train.index.max() >= prev_train_end  # anchored/expanding
        prev_train_end = train.index.max()


def test_oos_fraction_bounds_validated():
    with pytest.raises(ValueError):
        oos_split(_close(), oos_fraction=0.0)
    with pytest.raises(ValueError):
        oos_split(_close(), oos_fraction=1.0)
```

2. Run `uv run pytest tests/backtest/test_validation.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/validation.py`:

```python
"""Leakage and robustness discipline (Spec §5.4).

- shift_test: lag ALL inputs by one bar and re-run; if performance survives
  unchanged the strategy wasn't using future info, if it collapses there was
  leakage. We report both numbers plus a collapse flag.
- oos_split: chronological in-sample / out-of-sample cut; the OOS tail is
  NEVER touched during model selection.
- anchored_walk_forward: expanding train window, fixed-size forward test
  windows (anchored at the start).

Purging/embargo/CPCV are intentionally absent: no ML, no overlapping labels
in Phase 1 (Spec §16).
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd


def oos_split(
    series: pd.Series, oos_fraction: float = 0.25
) -> tuple[pd.Series, pd.Series]:
    """Chronological in-sample / out-of-sample split."""
    if not 0.0 < oos_fraction < 1.0:
        raise ValueError("oos_fraction must be in (0, 1)")
    cut = int(len(series) * (1.0 - oos_fraction))
    return series.iloc[:cut], series.iloc[cut:]


def shift_test(
    series: pd.Series,
    run: Callable[[pd.Series], float],
    lag: int = 1,
    collapse_tolerance: float = 0.5,
) -> dict[str, object]:
    """Run `run` on the series and on the series shifted by `lag` bars.

    `collapsed` is True when the shifted score drops to <= collapse_tolerance
    of the baseline magnitude — the signature of removed lookahead.
    """
    baseline = run(series)
    shifted = run(series.shift(lag).dropna())
    if baseline == 0:
        collapsed = shifted == 0
    else:
        collapsed = abs(shifted) <= collapse_tolerance * abs(baseline)
    return {"baseline": baseline, "shifted": shifted, "collapsed": collapsed}


def anchored_walk_forward(
    series: pd.Series, n_splits: int = 3, test_size: int = 252
) -> list[tuple[pd.Series, pd.Series]]:
    """Expanding train window + fixed forward test windows, anchored at start."""
    windows: list[tuple[pd.Series, pd.Series]] = []
    total = len(series)
    first_train = total - n_splits * test_size
    if first_train <= 0:
        raise ValueError("series too short for requested splits/test_size")
    for i in range(n_splits):
        train_end = first_train + i * test_size
        test_end = train_end + test_size
        windows.append((series.iloc[:train_end], series.iloc[train_end:test_end]))
    return windows
```

4. Run `uv run pytest tests/backtest/test_validation.py -q` — expect PASS (5 passed).

5. Run `backtest-methodology-reviewer` against `validation.py` (focus: shift-test direction correct, OOS strictly chronological, walk-forward anchored). Commit: `feat(backtest): add shift-test, OOS split, and anchored walk-forward`

---

## Task 10: Break-even-cost check

**Files:**
- Create: `src/signal_trader/backtest/breakeven.py`, `tests/backtest/test_breakeven.py`
- Modify: none

1. Write `tests/backtest/test_breakeven.py`:

```python
import pytest

from signal_trader.backtest.breakeven import breakeven_commission


def test_breakeven_found_for_decaying_sharpe():
    # sharpe falls linearly from +2 at cost 0 to -1 at cost 0.02
    def sharpe_at(commission: float) -> float:
        return 2.0 - 150.0 * commission

    be = breakeven_commission(sharpe_at, hi=0.02)
    assert be is not None
    assert abs(sharpe_at(be)) < 1e-3


def test_returns_none_when_sharpe_never_crosses_zero():
    def always_positive(commission: float) -> float:
        return 1.5

    assert breakeven_commission(always_positive, hi=0.02) is None


def test_rejects_nonpositive_starting_sharpe():
    def negative(commission: float) -> float:
        return -0.5

    with pytest.raises(ValueError):
        breakeven_commission(negative, hi=0.02)
```

2. Run `uv run pytest tests/backtest/test_breakeven.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/breakeven.py`:

```python
"""Break-even-cost check: at what per-trade commission does Sharpe hit 0?

A strategy that only works at unrealistically low costs is fragile. We
bisect on commission, assuming Sharpe is non-increasing in cost (true for a
trading strategy). Returns None if Sharpe stays positive across the range.
"""
from __future__ import annotations

from collections.abc import Callable


def breakeven_commission(
    sharpe_at: Callable[[float], float],
    lo: float = 0.0,
    hi: float = 0.05,
    tol: float = 1e-4,
    max_iter: int = 60,
) -> float | None:
    """Smallest commission at which `sharpe_at(commission)` == 0.

    Raises if Sharpe is already <= 0 at `lo` (nothing to break even from).
    """
    s_lo = sharpe_at(lo)
    if s_lo <= 0:
        raise ValueError("Sharpe must be positive at lo to find a break-even")
    if sharpe_at(hi) > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        s_mid = sharpe_at(mid)
        if abs(s_mid) < tol:
            return mid
        if s_mid > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
```

4. Run `uv run pytest tests/backtest/test_breakeven.py -q` — expect PASS (3 passed).

5. Commit: `feat(backtest): add break-even-cost bisection check`

---

## Task 11: Alpaca paper stub (mocked)

**Files:**
- Create: `src/signal_trader/paper/__init__.py`, `src/signal_trader/paper/alpaca/__init__.py`, `src/signal_trader/paper/alpaca/paper_stub.py`, `tests/paper/__init__.py`, `tests/paper/test_paper_stub.py`
- Modify: none

1. Write `tests/paper/test_paper_stub.py` (alpaca-py fully mocked — no live call, no keys):

```python
from unittest.mock import MagicMock, patch

import pytest

from signal_trader.paper.alpaca.paper_stub import AlpacaPaperStub


def test_submit_market_buy_builds_paper_request_and_returns_id():
    fake_client = MagicMock()
    fake_client.submit_order.return_value = MagicMock(id="order-123")
    with patch(
        "signal_trader.paper.alpaca.paper_stub.TradingClient",
        return_value=fake_client,
    ) as ctor:
        stub = AlpacaPaperStub(api_key="k", secret_key="s")
        order_id = stub.submit_market_buy("AAPL", qty=1)

    ctor.assert_called_once_with("k", "s", paper=True)
    assert order_id == "order-123"
    _, kwargs = fake_client.submit_order.call_args
    req = kwargs["order_data"]
    assert req.symbol == "AAPL"
    assert req.qty == 1


def test_missing_credentials_raise_before_any_network_call():
    with pytest.raises(ValueError):
        AlpacaPaperStub(api_key=None, secret_key=None)
```

2. Run `uv run pytest tests/paper/test_paper_stub.py -q` — expect FAIL.

3. Create `src/signal_trader/paper/__init__.py` (empty), `src/signal_trader/paper/alpaca/__init__.py` (empty), `tests/paper/__init__.py` (empty), and `src/signal_trader/paper/alpaca/paper_stub.py`:

```python
"""Thin Alpaca paper-trading stub (alpaca-py 0.43.4).

Phase 1 scope: push exactly one paper market order to prove the plumbing
(Spec §5.7). Always paper=True; keys come from .env via config, never
hard-coded. Full order routing / PnL is Phase 3. In tests TradingClient is
mocked — no live call ever.
"""
from __future__ import annotations

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


class AlpacaPaperStub:
    def __init__(self, api_key: str | None, secret_key: str | None):
        if not api_key or not secret_key:
            raise ValueError("Alpaca API key and secret required (set them in .env)")
        self._client = TradingClient(api_key, secret_key, paper=True)

    def submit_market_buy(self, symbol: str, qty: int = 1) -> str:
        """Submit a single paper day-order market buy; return the order id."""
        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        order = self._client.submit_order(order_data=request)
        return str(order.id)
```

4. Run `uv run pytest tests/paper/test_paper_stub.py -q` — expect PASS (2 passed).

5. Commit: `feat(paper): add mocked Alpaca paper market-buy stub`

---

## Task 12: CLI scripts + foundation report (both engines + benchmark + diff)

**Files:**
- Create: `src/signal_trader/backtest/report.py`, `scripts/backfill.py`, `scripts/run_backtest.py`, `tests/backtest/test_report.py`, `tests/test_scripts.py`
- Modify: none

1. Write `tests/backtest/test_report.py`:

```python
import numpy as np
import pandas as pd

from signal_trader.backtest.report import FoundationReport, build_foundation_report
from signal_trader.backtest.costs import CostModel


def _close(n=400, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.Series(100 * np.exp(rng.normal(0.0006, 0.01, n).cumsum()), index=idx)


def test_report_contains_both_engines_and_benchmark():
    rep = build_foundation_report(_close(), CostModel(0.001, 0.0005), lookback=50)
    assert isinstance(rep, FoundationReport)
    assert set(rep.engine_metrics) == {"backtesting.py", "vectorbt"}
    assert rep.benchmark_metrics is not None


def test_report_quantifies_vectorized_vs_event_driven_gap():
    rep = build_foundation_report(_close(), CostModel(0.001, 0.0005), lookback=50)
    # the headline artifact: a numeric Sharpe difference between engines
    assert isinstance(rep.vectorized_minus_event_driven_sharpe, float)


def test_render_text_mentions_after_cost_benchmark_and_both_engines():
    rep = build_foundation_report(_close(), CostModel(0.001, 0.0005), lookback=50)
    text = rep.render()
    assert "vectorbt" in text and "backtesting.py" in text
    assert "Buy & Hold (after costs)" in text
    assert "PSR" in text
```

2. Run `uv run pytest tests/backtest/test_report.py -q` — expect FAIL.

3. Create `src/signal_trader/backtest/report.py`:

```python
"""Foundation report: run the baseline through BOTH engines, compare to the
after-cost buy-and-hold benchmark, and quantify the headline artifact —
'vectorized looks better than event-driven on identical signals' (Spec §5).

Every number is after costs; every engine is shown with the full honest
metric set (never Sharpe alone).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from signal_trader.backtest.benchmark import buy_and_hold_equity
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.engine.backtesting_py import BacktestingPyAdapter
from signal_trader.backtest.engine.vectorbt_engine import VectorbtAdapter
from signal_trader.backtest.metrics import MetricsReport, compute_metrics


def _ohlcv_from_close(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": close.shift(1).fillna(close.iloc[0]),
            "High": close * 1.001,
            "Low": close * 0.999,
            "Close": close,
            "Volume": 1_000_000.0,
        }
    )


@dataclass
class FoundationReport:
    engine_metrics: dict[str, MetricsReport]
    benchmark_metrics: MetricsReport
    vectorized_minus_event_driven_sharpe: float

    def render(self) -> str:
        lines = ["=== Foundation Report (all figures after costs) ===", ""]
        for engine, m in self.engine_metrics.items():
            lines.append(
                f"[{engine}] CAGR={m.cagr:.3f} Sharpe={m.sharpe:.3f} "
                f"Sortino={m.sortino:.3f} Calmar={m.calmar:.3f} "
                f"MaxDD={m.max_drawdown:.3f} PSR={m.psr:.3f}"
            )
        b = self.benchmark_metrics
        lines.append(
            f"[Buy & Hold (after costs)] CAGR={b.cagr:.3f} Sharpe={b.sharpe:.3f} "
            f"Sortino={b.sortino:.3f} Calmar={b.calmar:.3f} "
            f"MaxDD={b.max_drawdown:.3f} PSR={b.psr:.3f}"
        )
        lines.append("")
        lines.append(
            "Artifact — vectorbt Sharpe minus backtesting.py Sharpe: "
            f"{self.vectorized_minus_event_driven_sharpe:+.3f} "
            "(positive = vectorized looks better than event-driven on the "
            "same signals; the realism gap, not an edge)."
        )
        return "\n".join(lines)


def build_foundation_report(
    close: pd.Series, cost_model: CostModel, lookback: int = 50
) -> FoundationReport:
    event = BacktestingPyAdapter(cost_model).run(
        _ohlcv_from_close(close), lookback=lookback
    )
    vector = VectorbtAdapter(cost_model).run(close, lookback=lookback)
    bench_equity = buy_and_hold_equity(close, cost_model)

    engine_metrics = {
        event.engine: compute_metrics(event.returns()),
        vector.engine: compute_metrics(vector.returns()),
    }
    benchmark_metrics = compute_metrics(bench_equity.pct_change().dropna())
    gap = engine_metrics["vectorbt"].sharpe - engine_metrics["backtesting.py"].sharpe
    return FoundationReport(
        engine_metrics=engine_metrics,
        benchmark_metrics=benchmark_metrics,
        vectorized_minus_event_driven_sharpe=gap,
    )
```

4. Run `uv run pytest tests/backtest/test_report.py -q` — expect PASS (3 passed).

5. Write `tests/test_scripts.py` (drives CLI entrypoints with a faked provider, no network):

```python
import sys
from unittest.mock import patch

import pandas as pd

import scripts.backfill as backfill
import scripts.run_backtest as run_backtest


class FakeProvider:
    def fetch(self, tickers, start, end):
        frames = []
        for t in tickers:
            idx = pd.date_range("2018-01-01", periods=400, freq="B")
            frames.append(pd.DataFrame({
                "ticker": t, "date": idx,
                "open": 100.0, "high": 101.0, "low": 99.0,
                "close": (100 + (idx - idx[0]).days * 0.05),
                "volume": 1e6,
            }))
        return pd.concat(frames, ignore_index=True)


def test_backfill_main_runs_with_faked_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "YFinanceProvider", FakeProvider)
    monkeypatch.setattr(backfill.config, "PARQUET_DIR", tmp_path / "bars")
    monkeypatch.setattr(backfill.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    with patch.object(sys, "argv", ["backfill.py", "--tickers", "AAPL", "MSFT"]):
        backfill.main()
    assert (tmp_path / "bars" / "AAPL.parquet").exists()


def test_run_backtest_main_prints_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_backtest, "YFinanceProvider", FakeProvider)
    monkeypatch.setattr(run_backtest.config, "PARQUET_DIR", tmp_path / "bars")
    monkeypatch.setattr(run_backtest.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    with patch.object(
        sys, "argv",
        ["run_backtest.py", "--ticker", "AAPL", "--lookback", "50"],
    ):
        run_backtest.main()
    out = capsys.readouterr().out
    assert "Foundation Report" in out
    assert "vectorbt" in out and "backtesting.py" in out
```

6. Run `uv run pytest tests/test_scripts.py -q` — expect FAIL.

7. Create `scripts/backfill.py`:

```python
"""CLI: fetch the universe (or given tickers) once and cache it.

    uv run python scripts/backfill.py --tickers AAPL MSFT
    uv run python scripts/backfill.py --limit 50
"""
from __future__ import annotations

import argparse

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.market_data.universe import load_sp500_tickers
from signal_trader.store.cache_service import CacheService


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill daily bars into cache")
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", default=config.DEFAULT_START)
    parser.add_argument("--end", default=config.DEFAULT_END)
    args = parser.parse_args()

    tickers = args.tickers or load_sp500_tickers(limit=args.limit)
    service = CacheService(
        YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH
    )
    service.backfill(tickers, args.start, args.end)
    print(f"Cached {len(tickers)} ticker(s) into {config.PARQUET_DIR}")


if __name__ == "__main__":
    main()
```

8. Create `scripts/run_backtest.py`:

```python
"""CLI: run the momentum baseline through BOTH engines and print the
foundation report (after-cost metrics + benchmark + the vectorized-vs-
event-driven gap).

    uv run python scripts/run_backtest.py --ticker AAPL --lookback 50
"""
from __future__ import annotations

import argparse

from signal_trader import config
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.report import build_foundation_report
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.store.cache_service import CacheService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the foundation backtest report")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--lookback", type=int, default=50)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--start", default=config.DEFAULT_START)
    parser.add_argument("--end", default=config.DEFAULT_END)
    args = parser.parse_args()

    service = CacheService(
        YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH
    )
    service.backfill([args.ticker], args.start, args.end)
    close = service.load_close_matrix([args.ticker], args.start, args.end)[
        args.ticker
    ].dropna()

    report = build_foundation_report(
        close,
        CostModel(commission_per_trade=args.commission, slippage=args.slippage),
        lookback=args.lookback,
    )
    print(report.render())


if __name__ == "__main__":
    main()
```

9. Run `uv run pytest tests/test_scripts.py -q` — expect PASS (2 passed).

10. Run the full suite and lint: `uv run pytest -q` (all green) and `uv run ruff check .` (clean). Run `backtest-methodology-reviewer` against `report.py` (focus: benchmark after costs, full metric set per engine, the gap is framed as a realism artifact not an edge). Commit: `feat(scripts): add backfill + foundation-report CLIs`

---

## Verification before completion (run before claiming Phase 1 done)

1. `uv run pytest -q` — paste the real summary line (expect all tests passing).
2. `uv run ruff check .` — expect "All checks passed".
3. One live smoke (manual, not in CI, not committed): `uv run python scripts/backfill.py --tickers AAPL --start 2020-01-01 --end 2021-01-01` then `uv run python scripts/run_backtest.py --ticker AAPL` — confirm a rendered report with both engines, the after-cost benchmark line, and a non-trivial `vectorbt minus backtesting.py` Sharpe gap.
4. Run `backtest-methodology-reviewer` once across the whole `backtest/` tree; resolve any 🔴/🟡 before the phase-gate report.
5. Write the phase-gate report (Spec working-method): what was measured, the engine gap number, honest caveats (survivorship, auto_adjust restatement). Await Nico's go before Phase 2.

---

### Critical Files for Implementation

- /home/nicosutheimer/private/signal-trader-demo/src/signal_trader/backtest/engine/backtesting_py.py
- /home/nicosutheimer/private/signal-trader-demo/src/signal_trader/backtest/engine/vectorbt_engine.py
- /home/nicosutheimer/private/signal-trader-demo/src/signal_trader/backtest/metrics.py
- /home/nicosutheimer/private/signal-trader-demo/src/signal_trader/store/cache_service.py
- /home/nicosutheimer/private/signal-trader-demo/src/signal_trader/backtest/report.py

---

## Implementation Notes / Outcome (2026-06-17)

**Status: Phase 1 complete.** All 13 tasks (T0–T12) implemented TDD-first, subagent-driven, on branch `feat/phase-1-foundation`. Final state: **71 tests pass**, `ruff` clean, end-to-end live smoke (AAPL 2020–2024) renders the foundation report.

**Live smoke result (honest finding):** the momentum baseline *underperforms* buy-and-hold after costs — exactly what the harness exists to surface.

| | CAGR | Sharpe | Sortino | Calmar | MaxDD | PSR |
|---|---|---|---|---|---|---|
| backtesting.py | 0.150 | 0.831 | 1.231 | 0.504 | -0.298 | 0.996 |
| vectorbt | 0.146 | 0.810 | 1.199 | 0.482 | -0.303 | 0.995 |
| Buy & Hold (after costs) | 0.277 | 0.987 | 1.459 | 0.719 | -0.385 | 0.999 |

The vectorbt-vs-backtesting.py Sharpe gap was small and **data-dependent** (slightly negative here) — the realism gap is real but not guaranteed in the "vectorized looks better" direction. (Numbers predate the `bf7bef6` flat-bar fix, which slightly narrows the gap; qualitative result unchanged.)

**Two methodology gates caught real invalidating bugs** (the point of the rigor):
- The original **shift-test was a no-op** (lagged the whole price series → couldn't detect same-series lookahead). Redesigned to lag the signal relative to its returns; now proven both ways (leaky `sign(returns)` → `collapsed=True`; clean momentum → `collapsed=False`). Commit `8eadaf0`.
- **CAGR/Calmar were understated ~29%** (`qs.stats.cagr` used calendar-days/252). Replaced with trading-year compounding. Commit `8eadaf0`.
- Also fixed in review: range-aware cache (no silent truncation), `load_close_matrix` raises on missing tickers, `fetched_at` preserved, warmup-exit masking, cross-engine trade-count parity test, hidden synthetic spread removed.

**Deviations from the plan (all noted in commits):**
- Momentum baseline is **state-based** (in-position while above SMA), not crossover — the plan's crossover code contradicted its own tests. One-bar leakage shift identical.
- `quantstats-reloaded` 0.1.0 lacks `cagr(periods=)` / `sharpe(annualize=)` — adapted to real signatures; CAGR/Calmar computed manually.
- The reviewer-claimed PSR sqrt-of-negative is mathematically unreachable from valid sample moments (Pearson bound) — guard kept as defensive engineering, not a real trigger.
- SQLite `PriceBar` collapses `adj_close` into `close` (yfinance `auto_adjust`); add a nullable `adj_close` column when upgrading to Tiingo.

**Open items carried to later phases:** surface data-lag/hit-rate in UI (Phase 3); expose walk-forward params in the CLI; `adj_close` column for the Tiingo upgrade; Alpaca/SEC credentials in `.env` (Open Inputs in `PROJECT.md`).
