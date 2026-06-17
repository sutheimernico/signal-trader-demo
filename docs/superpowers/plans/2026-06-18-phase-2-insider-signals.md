# Phase 2 — Insider Signals (Track 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`. Execute this plan strictly TDD, one task at a time, in order. For each numbered step: write the failing test first, run it and confirm it FAILS for the stated reason, then write the minimal implementation, run again and confirm it PASSES, then commit with the exact message given. Never write implementation before its test. After every task flagged **[methodology-review]**, dispatch the `backtest-methodology-reviewer` agent (`.claude/agents/`) on the diff before committing — it hunts lookahead, survivorship, missing costs, PIT violations, benchmark-discipline. **No test may make a live network/SDK call**: edgartools is ALWAYS faked or mocked in tests; the only live SEC contact is the separate smoke script run by the controller (needs `SEC_IDENTITY` in `.env`). All code, identifiers, comments, commit messages in English; reply to Nico in German. Keep types and signatures identical across tasks — the DTOs defined in Task 2 are the contract every later task consumes.

## Goal

Build Track 1 (Insider Signals) on top of the Phase-1 foundation: ingest SEC Form 4 filings behind a source seam, filter signal from noise (open-market purchases, opportunistic-only, clustered, 10b5-1 excluded), persist every observation point-in-time (`timestamp_known` = filing date, never the trade date), consolidate per stock, score each source's hit-rate / forward-return with its data-lag made visible, and run an insider strategy through BOTH existing engines (`backtesting.py` + `vectorbt`) with costs, after-cost benchmark, and the shift/OOS/walk-forward discipline already built in Phase 1. The deliverable is an honest measurement of the insider signal, not an edge claim.

## Architecture

Five layers, reusing Phase 1 wholesale:

```
[ sources/ ]          InsiderSource Protocol + edgartools adapter -> InsiderObservation DTOs   (Task 2-3)
[ signals/insider/ ]  pure filters (P-code, 10b5-1, opportunistic, cluster, small-cap tilt)    (Task 4-5)
[ store/ ]            SignalStore + SourceScoreStore (extend existing SQLite store)             (Task 6, 9)
[ signals/consolidate/] per-ticker consolidated_score from contributing signals               (Task 7)
[ signals/scoring/ ]  forward-return from bar-cache, hit-rate + avg_forward_return per source   (Task 8-9)
[ strategy/longterm/] InsiderStrategy: consolidated signals -> entries/exits, PIT (known+1)     (Task 10)
[ backtest/engine/* ] REUSED unchanged — both engines consume the strategy's entries/exits      (Task 11)
[ scripts/ ]          ingest CLI + insider report CLI + live SEC smoke (controller-only)         (Task 12)
```

Hard seam: edgartools is imported ONLY in `sources/edgar_form4.py`. Filters, persistence, consolidation, scoring, and strategy operate exclusively on our own `InsiderObservation` / `InsiderSignal` dataclasses, so every test downstream of the adapter is pure and offline.

## Tech Stack

Python ≥3.11 · `edgartools==5.36.0` (pinned; new dependency — only SEC Form 4 client that returns typed transactions; `set_identity` satisfies SEC fair-access, ≤10 req/s) · existing SQLite store (`PriceBarStore` pattern) · existing `CacheService.load_close_matrix` for prices · existing `backtest/{costs,benchmark,metrics,validation,result}.py` and both engine adapters · pytest + ruff. No new backtest machinery is built — Phase 1 modules are reused verbatim.

Verified edgartools API (5.36.0): `from edgar import set_identity, Company`; `Company(ticker).get_filings(form="4", filing_date="YYYY-MM-DD:YYYY-MM-DD")` returns an iterable `Filings`; each `Filing` has `.filing_date` (str `YYYY-MM-DD`), `.accession_no`, `.obj()`; `filing.obj()` returns a Form 4 object exposing `.market_trades` (DataFrame with columns `Date, Shares, Price, AcquiredDisposed, Code, Remaining, Security`), `.has_10b5_1_plan` (True/False/None), `.position` (role string), `.reporting_owner_name`, `.issuer_ticker`.

---

## File Structure

**New source files**

| File | Single responsibility |
|---|---|
| `src/signal_trader/sources/__init__.py` | Package marker. |
| `src/signal_trader/sources/insider_source.py` | `InsiderSource` Protocol + `InsiderObservation` DTO (vendor-neutral contract). |
| `src/signal_trader/sources/edgar_form4.py` | edgartools adapter: Form 4 filings → `InsiderObservation` list. The ONLY file importing `edgar`. |
| `src/signal_trader/signals/insider/__init__.py` | Package marker. |
| `src/signal_trader/signals/insider/filters.py` | Pure filters: P-code, drop 10b5-1, drop options/vesting/awards. |
| `src/signal_trader/signals/insider/opportunistic.py` | Cohen/Malloy/Pomorski routine-vs-opportunistic classifier. |
| `src/signal_trader/signals/insider/cluster.py` | Cluster detection (≥N insiders in a window) + optional small-cap tilt. |
| `src/signal_trader/signals/insider/pipeline.py` | Compose adapter→filters→cluster into `InsiderSignal` list. |
| `src/signal_trader/signals/consolidate/__init__.py` | Package marker. |
| `src/signal_trader/signals/consolidate/consolidate.py` | Per-ticker `consolidated_score` from contributing signals. |
| `src/signal_trader/signals/scoring/__init__.py` | Package marker. |
| `src/signal_trader/signals/scoring/forward_return.py` | Forward return per signal from the bar-cache, anchored at `timestamp_known`. |
| `src/signal_trader/signals/scoring/source_score.py` | Hit-rate + avg_forward_return + data-lag per source/window. |
| `src/signal_trader/strategy/longterm/__init__.py` | Package marker. |
| `src/signal_trader/strategy/longterm/insider_strategy.py` | Consolidated signals → PIT entries/exits for both engines. |
| `src/signal_trader/store/signal_store.py` | SQLite `Signal` + `SourceScore` persistence (extends the store package). |

**New scripts**

| File | Responsibility |
|---|---|
| `scripts/ingest_insider.py` | CLI: faked-in-tests ingest of Form 4 → filter → persist signals. |
| `scripts/run_insider_report.py` | CLI: consolidated insider strategy through both engines + hit-rate table. |
| `scripts/sec_smoke.py` | Controller-only live SEC smoke (needs `SEC_IDENTITY`); never run in pytest. |

**New tests (mirrored)**

`tests/sources/test_insider_source.py`, `tests/sources/test_edgar_form4.py`, `tests/signals/insider/test_filters.py`, `tests/signals/insider/test_opportunistic.py`, `tests/signals/insider/test_cluster.py`, `tests/signals/insider/test_pipeline.py`, `tests/signals/consolidate/test_consolidate.py`, `tests/signals/scoring/test_forward_return.py`, `tests/signals/scoring/test_source_score.py`, `tests/strategy/longterm/test_insider_strategy.py`, `tests/strategy/longterm/test_insider_engine_run.py`, `tests/store/test_signal_store.py`, `tests/test_insider_scripts.py`. Plus `__init__.py` markers for every new test package directory.

**Modified files**

`pyproject.toml` (pin edgartools), `src/signal_trader/config.py` (read `SEC_IDENTITY`), `.env.example` (document `SEC_IDENTITY`), `README.md` (insider data-lag caveat), `tests/test_config.py` (cover `sec_identity`).

---

## Task 1: Deps & config — pin edgartools, read SEC_IDENTITY

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/signal_trader/config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py` (extend)

**Steps:**

1. Add a failing test to `tests/test_config.py`:
```python
def test_sec_identity_defaults_to_none_when_env_absent(monkeypatch):
    monkeypatch.delenv("SEC_IDENTITY", raising=False)
    assert config.sec_identity() is None


def test_sec_identity_read_from_env(monkeypatch):
    monkeypatch.setenv("SEC_IDENTITY", "Nico Sutheimer nico@example.com")
    assert config.sec_identity() == "Nico Sutheimer nico@example.com"
```

2. Run `uv run pytest tests/test_config.py -q` → expect FAIL (`AttributeError: module 'signal_trader.config' has no attribute 'sec_identity'`).

3. Add to `src/signal_trader/config.py`, directly after `alpaca_credentials`:
```python
def sec_identity() -> str | None:
    """Return the SEC fair-access identity ('Name email') from the environment.

    edgartools requires this via set_identity; SEC mandates a contactable
    User-Agent and caps requests at ~10/s. None when unset — callers that hit
    the network must raise rather than contact SEC anonymously.
    """
    return os.environ.get("SEC_IDENTITY")
```

4. Pin the dependency in `pyproject.toml` under `dependencies` (alphabetical-ish, after `backtesting`):
```toml
    "edgartools==5.36.0",
```
Then run `uv lock` and `uv sync` so the lockfile and venv match (state-changing: announce to controller; this writes `uv.lock` and `.venv`).

5. Add to `.env.example`:
```
# SEC fair-access identity for edgartools (Form 4). Format: "Name email@example.com".
SEC_IDENTITY=
```

6. Run `uv run pytest tests/test_config.py -q` → expect PASS. Run `uv run ruff check .` → expect clean.

7. `Commit: \`chore(deps): pin edgartools and read SEC_IDENTITY from env\``

---

## Task 2: InsiderSource seam + InsiderObservation DTO

Defines the vendor-neutral contract every downstream task consumes. No edgartools here.

**Files:**
- Create: `src/signal_trader/sources/__init__.py` (empty)
- Create: `src/signal_trader/sources/insider_source.py`
- Create: `tests/sources/__init__.py` (empty)
- Test: `tests/sources/test_insider_source.py`

**Steps:**

1. Write failing test `tests/sources/test_insider_source.py`:
```python
import datetime as dt

import pytest

from signal_trader.sources.insider_source import InsiderObservation, InsiderSource


def _obs(**over):
    base = dict(
        ticker="AAPL",
        reporting_owner="Jane Doe",
        role="Director",
        transaction_code="P",
        acquired_disposed="A",
        shares=1000.0,
        price=150.0,
        timestamp_event=dt.date(2024, 1, 10),
        timestamp_known=dt.date(2024, 1, 12),
        is_10b5_1=False,
        accession_no="0000000000-24-000001",
    )
    base.update(over)
    return InsiderObservation(**base)


def test_observation_is_frozen_and_holds_fields():
    obs = _obs()
    assert obs.ticker == "AAPL"
    assert obs.transaction_code == "P"
    assert obs.timestamp_known == dt.date(2024, 1, 12)
    with pytest.raises(Exception):
        obs.ticker = "MSFT"  # frozen


def test_known_must_not_predate_event():
    with pytest.raises(ValueError):
        _obs(timestamp_event=dt.date(2024, 1, 12), timestamp_known=dt.date(2024, 1, 10))


def test_notional_is_shares_times_price():
    assert _obs(shares=10.0, price=5.0).notional == 50.0


def test_protocol_is_runtime_checkable():
    class Dummy:
        def fetch(self, tickers, start, end):
            return []
    assert isinstance(Dummy(), InsiderSource)
```

2. Run `uv run pytest tests/sources/test_insider_source.py -q` → expect FAIL (module missing).

3. Implement `src/signal_trader/sources/insider_source.py`:
```python
"""Vendor-neutral insider-source seam (analogous to PriceProvider).

InsiderObservation is the single contract every downstream filter, store,
and scorer consumes — edgartools types never leak past the adapter. The
point-in-time invariant lives here: timestamp_known (filing date) is when an
OUTSIDER could act; timestamp_event (trade date) is private until filed and
must never drive a trade. We enforce known >= event at construction.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class InsiderObservation:
    ticker: str
    reporting_owner: str
    role: str
    transaction_code: str
    acquired_disposed: str  # "A" acquired / "D" disposed
    shares: float
    price: float
    timestamp_event: dt.date  # trade date (private until filed)
    timestamp_known: dt.date  # filing date (point-in-time)
    is_10b5_1: bool
    accession_no: str

    def __post_init__(self) -> None:
        if self.timestamp_known < self.timestamp_event:
            raise ValueError(
                "timestamp_known (filing) must not predate timestamp_event (trade)"
            )

    @property
    def notional(self) -> float:
        return self.shares * self.price


@runtime_checkable
class InsiderSource(Protocol):
    def fetch(
        self, tickers: list[str], start: str, end: str
    ) -> list[InsiderObservation]:
        """Return insider observations whose FILING date is in [start, end]."""
        ...
```

4. Run `uv run pytest tests/sources/test_insider_source.py -q` → expect PASS. `uv run ruff check .` → clean.

5. `Commit: \`feat(sources): add InsiderSource seam and InsiderObservation DTO\``

---

## Task 3: edgartools Form 4 adapter  **[methodology-review]**

The only file importing `edgar`. In tests, the edgartools surface is faked entirely — no live call.

**Files:**
- Create: `src/signal_trader/sources/edgar_form4.py`
- Test: `tests/sources/test_edgar_form4.py`

**Steps:**

1. Write failing test `tests/sources/test_edgar_form4.py`. It fakes `set_identity`, `Company`, the `Filings` iterable, each `Filing` (`.filing_date`, `.accession_no`, `.obj()`), and the Form 4 object (`.market_trades` DataFrame, `.has_10b5_1_plan`, `.position`, `.reporting_owner_name`, `.issuer_ticker`):
```python
import datetime as dt
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from signal_trader.sources.edgar_form4 import EdgarForm4Source


def _form4_obj(code="P", acq="A", has_plan=False):
    obj = MagicMock()
    obj.has_10b5_1_plan = has_plan
    obj.position = "Director"
    obj.reporting_owner_name = "Jane Doe"
    obj.issuer_ticker = "AAPL"
    obj.market_trades = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-10")],
            "Shares": [1000.0],
            "Price": [150.0],
            "AcquiredDisposed": [acq],
            "Code": [code],
            "Remaining": [5000.0],
            "Security": ["Common Stock"],
        }
    )
    return obj


def _filing(obj, filing_date="2024-01-12", accession="0000000000-24-000001"):
    f = MagicMock()
    f.filing_date = filing_date
    f.accession_no = accession
    f.obj.return_value = obj
    return f


def _patched_company(filings):
    company = MagicMock()
    company.get_filings.return_value = filings
    return company


def test_fetch_maps_form4_rows_to_observations():
    filings = [_filing(_form4_obj())]
    with patch("signal_trader.sources.edgar_form4.set_identity") as si, patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company(filings),
    ):
        src = EdgarForm4Source(identity="Nico Sutheimer nico@example.com")
        out = src.fetch(["AAPL"], "2024-01-01", "2024-01-31")

    si.assert_called_once_with("Nico Sutheimer nico@example.com")
    assert len(out) == 1
    obs = out[0]
    assert obs.ticker == "AAPL"
    assert obs.transaction_code == "P"
    assert obs.acquired_disposed == "A"
    assert obs.shares == 1000.0
    assert obs.price == 150.0
    assert obs.timestamp_event == dt.date(2024, 1, 10)
    assert obs.timestamp_known == dt.date(2024, 1, 12)
    assert obs.is_10b5_1 is False
    assert obs.role == "Director"
    assert obs.accession_no == "0000000000-24-000001"


def test_fetch_passes_filing_date_range_to_get_filings():
    company = _patched_company([])
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company", return_value=company
    ):
        EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-06-30")
    _, kwargs = company.get_filings.call_args
    assert kwargs["form"] == "4"
    assert kwargs["filing_date"] == "2024-01-01:2024-06-30"


def test_multi_row_form4_yields_one_observation_per_trade():
    obj = _form4_obj()
    obj.market_trades = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-10"), pd.Timestamp("2024-01-10")],
            "Shares": [1000.0, 500.0],
            "Price": [150.0, 151.0],
            "AcquiredDisposed": ["A", "A"],
            "Code": ["P", "P"],
            "Remaining": [5000.0, 5500.0],
            "Security": ["Common Stock", "Common Stock"],
        }
    )
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company([_filing(obj)]),
    ):
        out = EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-01-31")
    assert len(out) == 2
    assert {o.shares for o in out} == {1000.0, 500.0}


def test_empty_identity_raises_before_network():
    with pytest.raises(ValueError):
        EdgarForm4Source(identity=None)


def test_unparseable_filing_is_skipped_not_silently_truncated(caplog):
    bad = _filing(_form4_obj())
    bad.obj.side_effect = RuntimeError("parse error")
    good = _filing(_form4_obj(), filing_date="2024-01-15", accession="acc-2")
    with patch("signal_trader.sources.edgar_form4.set_identity"), patch(
        "signal_trader.sources.edgar_form4.Company",
        return_value=_patched_company([bad, good]),
    ):
        out = EdgarForm4Source(identity="X y@z.com").fetch(["AAPL"], "2024-01-01", "2024-01-31")
    assert len(out) == 1  # good one survives
    assert any("skip" in r.message.lower() for r in caplog.records)
```

2. Run `uv run pytest tests/sources/test_edgar_form4.py -q` → expect FAIL (module missing).

3. Implement `src/signal_trader/sources/edgar_form4.py`:
```python
"""edgartools-backed Form 4 source (edgartools 5.36.0).

The ONLY module importing `edgar`. It maps SEC Form 4 filings to
vendor-neutral InsiderObservation DTOs. Point-in-time: timestamp_known is the
FILING date (filing.filing_date), the first instant an outsider could act;
timestamp_event is the trade date inside the filing. set_identity satisfies
SEC fair access. In tests every edgartools symbol is mocked — no live call.

A filing that fails to parse is logged and SKIPPED, never silently dropped:
truncation that hides data loss is forbidden (Spec iron principles).
"""
from __future__ import annotations

import datetime as dt
import logging

from edgar import Company, set_identity

from signal_trader.sources.insider_source import InsiderObservation

_LOG = logging.getLogger(__name__)


def _to_date(value: object) -> dt.date:
    """Coerce edgartools date-ish values (str 'YYYY-MM-DD' or Timestamp)."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


class EdgarForm4Source:
    """Fetch Form 4 filings per ticker and flatten their trades to DTOs."""

    def __init__(self, identity: str | None):
        if not identity:
            raise ValueError(
                "SEC identity required (set SEC_IDENTITY in .env); refusing "
                "to contact SEC anonymously"
            )
        self._identity = identity

    def fetch(
        self, tickers: list[str], start: str, end: str
    ) -> list[InsiderObservation]:
        set_identity(self._identity)
        observations: list[InsiderObservation] = []
        for ticker in tickers:
            filings = Company(ticker).get_filings(
                form="4", filing_date=f"{start}:{end}"
            )
            for filing in filings:
                try:
                    observations.extend(self._observations_from_filing(ticker, filing))
                except Exception as exc:  # noqa: BLE001 - log + skip, never truncate silently
                    _LOG.warning(
                        "skip unparseable Form 4 %s for %s: %s",
                        getattr(filing, "accession_no", "?"),
                        ticker,
                        exc,
                    )
        return observations

    def _observations_from_filing(self, ticker, filing) -> list[InsiderObservation]:
        obj = filing.obj()
        known = _to_date(filing.filing_date)
        trades = obj.market_trades
        out: list[InsiderObservation] = []
        for row in trades.itertuples(index=False):
            out.append(
                InsiderObservation(
                    ticker=str(obj.issuer_ticker or ticker),
                    reporting_owner=str(obj.reporting_owner_name),
                    role=str(obj.position),
                    transaction_code=str(row.Code),
                    acquired_disposed=str(row.AcquiredDisposed),
                    shares=float(row.Shares),
                    price=float(row.Price),
                    timestamp_event=_to_date(row.Date),
                    timestamp_known=known,
                    is_10b5_1=bool(obj.has_10b5_1_plan),
                    accession_no=str(filing.accession_no),
                )
            )
        return out
```

4. Run `uv run pytest tests/sources/test_edgar_form4.py -q` → expect PASS. `uv run ruff check .` → clean.

5. Dispatch `backtest-methodology-reviewer` on the diff (PIT correctness: known=filing date, event=trade date; no silent truncation). Address findings.

6. `Commit: \`feat(sources): edgartools Form 4 adapter to InsiderObservation\``

---

## Task 4: Noise filters — P-code, 10b5-1, options/vesting/awards

**Files:**
- Create: `src/signal_trader/signals/insider/__init__.py` (empty)
- Create: `src/signal_trader/signals/insider/filters.py`
- Create: `tests/signals/__init__.py`, `tests/signals/insider/__init__.py` (empty)
- Test: `tests/signals/insider/test_filters.py`

**Steps:**

1. Write failing test `tests/signals/insider/test_filters.py`:
```python
import datetime as dt

from signal_trader.signals.insider.filters import keep_open_market_purchases
from signal_trader.sources.insider_source import InsiderObservation


def _obs(code="P", acq="A", plan=False, **over):
    base = dict(
        ticker="AAPL", reporting_owner="X", role="Director",
        transaction_code=code, acquired_disposed=acq, shares=100.0, price=10.0,
        timestamp_event=dt.date(2024, 1, 10), timestamp_known=dt.date(2024, 1, 12),
        is_10b5_1=plan, accession_no="a",
    )
    base.update(over)
    return InsiderObservation(**base)


def test_keeps_plain_open_market_purchase():
    assert keep_open_market_purchases([_obs()]) == [_obs()]


def test_drops_sales_and_non_p_codes():
    kept = keep_open_market_purchases([_obs(code="S"), _obs(code="M"), _obs(code="A")])
    assert kept == []


def test_drops_acquisitions_that_are_not_acquired_flag():
    assert keep_open_market_purchases([_obs(code="P", acq="D")]) == []


def test_drops_10b5_1_plan_trades():
    assert keep_open_market_purchases([_obs(plan=True)]) == []


def test_keeps_only_qualifying_rows_from_mixed_batch():
    kept = keep_open_market_purchases(
        [_obs(), _obs(code="S"), _obs(plan=True), _obs(code="P", acq="A", shares=5.0)]
    )
    assert len(kept) == 2
```

2. Run `uv run pytest tests/signals/insider/test_filters.py -q` → expect FAIL (module missing).

3. Implement `src/signal_trader/signals/insider/filters.py`:
```python
"""Signal-vs-noise filters for insider observations (Spec §12).

Keep only what is informative for an outsider: transaction code "P"
(open-market purchase), genuinely acquired (AcquiredDisposed == "A"), and NOT
executed under a 10b5-1 plan (those are pre-scheduled, near-zero signal).
Sales, option exercises (M), grants/awards (A-code), vesting, and dispositions
are dropped — purchases inform, sales are noise (Cohen/Malloy/Pomorski).
"""
from __future__ import annotations

from signal_trader.sources.insider_source import InsiderObservation

_OPEN_MARKET_PURCHASE = "P"
_ACQUIRED = "A"


def keep_open_market_purchases(
    observations: list[InsiderObservation],
) -> list[InsiderObservation]:
    """Return only open-market, non-10b5-1, acquired purchases."""
    return [
        o
        for o in observations
        if o.transaction_code == _OPEN_MARKET_PURCHASE
        and o.acquired_disposed == _ACQUIRED
        and not o.is_10b5_1
    ]
```

4. Run `uv run pytest tests/signals/insider/test_filters.py -q` → expect PASS. `uv run ruff check .` → clean.

5. `Commit: \`feat(signals): filter insider noise to open-market purchases\``

---

## Task 5: Opportunistic-vs-routine + cluster + small-cap tilt  **[methodology-review]**

**Files:**
- Create: `src/signal_trader/signals/insider/opportunistic.py`
- Create: `src/signal_trader/signals/insider/cluster.py`
- Test: `tests/signals/insider/test_opportunistic.py`
- Test: `tests/signals/insider/test_cluster.py`

**Steps:**

1. Write failing test `tests/signals/insider/test_opportunistic.py`:
```python
import datetime as dt

from signal_trader.signals.insider.opportunistic import keep_opportunistic
from signal_trader.sources.insider_source import InsiderObservation


def _obs(owner, ticker, year, month, day=10):
    return InsiderObservation(
        ticker=ticker, reporting_owner=owner, role="Director",
        transaction_code="P", acquired_disposed="A", shares=100.0, price=10.0,
        timestamp_event=dt.date(year, month, day),
        timestamp_known=dt.date(year, month, day + 2),
        is_10b5_1=False, accession_no=f"{owner}-{year}-{month}",
    )


def test_drops_three_year_same_month_routine_trader():
    # Same owner+ticker, January in 2021, 2022, 2023 -> routine -> all dropped
    hist = [_obs("Jane", "AAPL", y, 1) for y in (2021, 2022, 2023)]
    assert keep_opportunistic(hist) == []


def test_keeps_irregular_trader():
    hist = [_obs("Bob", "AAPL", 2021, 3), _obs("Bob", "AAPL", 2022, 7)]
    assert len(keep_opportunistic(hist)) == 2


def test_routine_classification_is_per_owner_ticker_not_global():
    routine = [_obs("Jane", "AAPL", y, 1) for y in (2021, 2022, 2023)]
    one_off = [_obs("Jane", "MSFT", 2023, 1)]
    kept = keep_opportunistic(routine + one_off)
    assert kept == one_off


def test_only_drops_the_routine_month_not_other_months():
    routine_jan = [_obs("Jane", "AAPL", y, 1) for y in (2021, 2022, 2023)]
    other = [_obs("Jane", "AAPL", 2023, 6)]
    kept = keep_opportunistic(routine_jan + other)
    assert kept == other
```

2. Run → expect FAIL. Implement `src/signal_trader/signals/insider/opportunistic.py`:
```python
"""Routine-vs-opportunistic classifier (Cohen/Malloy/Pomorski, JF 2012).

An (owner, ticker) who trades in the SAME calendar month for 3+ consecutive
years is "routine" — predictable, near-zero alpha — and those routine-month
trades are dropped. Everything else is "opportunistic" and kept. We classify
per (owner, ticker, month) using the trade date (timestamp_event); this is a
property of the trade pattern, not a point-in-time trading decision, so using
event time here is correct.
"""
from __future__ import annotations

from collections import defaultdict

from signal_trader.sources.insider_source import InsiderObservation

_ROUTINE_CONSECUTIVE_YEARS = 3


def _routine_keys(
    observations: list[InsiderObservation],
) -> set[tuple[str, str, int]]:
    years_by_key: dict[tuple[str, str, int], set[int]] = defaultdict(set)
    for o in observations:
        key = (o.reporting_owner, o.ticker, o.timestamp_event.month)
        years_by_key[key].add(o.timestamp_event.year)
    routine: set[tuple[str, str, int]] = set()
    for key, years in years_by_key.items():
        if _has_consecutive_run(years, _ROUTINE_CONSECUTIVE_YEARS):
            routine.add(key)
    return routine


def _has_consecutive_run(years: set[int], length: int) -> bool:
    return any(all((y + i) in years for i in range(length)) for y in years)


def keep_opportunistic(
    observations: list[InsiderObservation],
) -> list[InsiderObservation]:
    """Drop trades whose (owner, ticker, month) is a routine 3-year pattern."""
    routine = _routine_keys(observations)
    return [
        o
        for o in observations
        if (o.reporting_owner, o.ticker, o.timestamp_event.month) not in routine
    ]
```

3. Run `uv run pytest tests/signals/insider/test_opportunistic.py -q` → expect PASS.

4. Write failing test `tests/signals/insider/test_cluster.py`:
```python
import datetime as dt

from signal_trader.signals.insider.cluster import (
    cluster_purchases,
    keep_small_cap,
)
from signal_trader.sources.insider_source import InsiderObservation


def _obs(owner, ticker, known_day, price=10.0, shares=100.0):
    return InsiderObservation(
        ticker=ticker, reporting_owner=owner, role="Director",
        transaction_code="P", acquired_disposed="A", shares=shares, price=price,
        timestamp_event=dt.date(2024, 1, known_day),
        timestamp_known=dt.date(2024, 1, known_day),
        is_10b5_1=False, accession_no=f"{owner}-{known_day}",
    )


def test_cluster_requires_min_distinct_insiders_in_window():
    obs = [_obs("A", "AAPL", 1), _obs("B", "AAPL", 3), _obs("C", "AAPL", 5)]
    clusters = cluster_purchases(obs, window_days=10, min_insiders=3)
    assert len(clusters) == 1
    assert clusters[0].ticker == "AAPL"
    assert clusters[0].n_insiders == 3


def test_no_cluster_when_window_too_narrow():
    obs = [_obs("A", "AAPL", 1), _obs("B", "AAPL", 3), _obs("C", "AAPL", 20)]
    assert cluster_purchases(obs, window_days=5, min_insiders=3) == []


def test_same_insider_counted_once():
    obs = [_obs("A", "AAPL", 1), _obs("A", "AAPL", 2), _obs("A", "AAPL", 3)]
    assert cluster_purchases(obs, window_days=10, min_insiders=3) == []


def test_cluster_known_date_is_latest_filing_in_window():
    obs = [_obs("A", "AAPL", 1), _obs("B", "AAPL", 4), _obs("C", "AAPL", 6)]
    clusters = cluster_purchases(obs, window_days=10, min_insiders=3)
    assert clusters[0].timestamp_known == dt.date(2024, 1, 6)


def test_small_cap_tilt_filters_by_price_proxy_threshold():
    cheap = _obs("A", "PENNY", 1, price=3.0)
    pricey = _obs("B", "MEGA", 1, price=400.0)
    kept = keep_small_cap([cheap, pricey], max_price=50.0)
    assert kept == [cheap]
```

5. Run → expect FAIL. Implement `src/signal_trader/signals/insider/cluster.py`:
```python
"""Cluster detection + optional small-cap tilt (Spec §12).

A cluster is >= min_insiders DISTINCT reporting owners buying the same ticker
within a rolling window measured in FILING (known) days — the point-in-time
horizon an outsider observes. The cluster's known date is the LATEST filing in
the window: the cluster is not 'known' until its final member has filed, so
trading earlier would be lookahead.

Small-cap tilt: a deliberately crude price proxy (Spec keeps it optional). We
have no free survivorship-clean market-cap feed, so a low share price is used
as a stand-in and documented as such — never presented as true market cap.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from signal_trader.sources.insider_source import InsiderObservation


@dataclass(frozen=True)
class InsiderCluster:
    ticker: str
    n_insiders: int
    timestamp_known: dt.date  # latest filing in the window (PIT)
    members: tuple[InsiderObservation, ...]


def cluster_purchases(
    observations: list[InsiderObservation],
    window_days: int = 10,
    min_insiders: int = 3,
) -> list[InsiderCluster]:
    """Detect, per ticker, the first window with >= min_insiders distinct owners."""
    clusters: list[InsiderCluster] = []
    by_ticker: dict[str, list[InsiderObservation]] = {}
    for o in observations:
        by_ticker.setdefault(o.ticker, []).append(o)
    for ticker, obs in by_ticker.items():
        obs = sorted(obs, key=lambda o: o.timestamp_known)
        for i, anchor in enumerate(obs):
            window = [
                o
                for o in obs[i:]
                if (o.timestamp_known - anchor.timestamp_known).days <= window_days
            ]
            owners = {o.reporting_owner for o in window}
            if len(owners) >= min_insiders:
                clusters.append(
                    InsiderCluster(
                        ticker=ticker,
                        n_insiders=len(owners),
                        timestamp_known=max(o.timestamp_known for o in window),
                        members=tuple(window),
                    )
                )
                break
    return clusters


def keep_small_cap(
    observations: list[InsiderObservation], max_price: float
) -> list[InsiderObservation]:
    """Crude small-cap tilt by share price (proxy only, not market cap)."""
    return [o for o in observations if o.price <= max_price]
```

6. Run `uv run pytest tests/signals/insider/test_cluster.py -q` → expect PASS. `uv run ruff check .` → clean.

7. Dispatch `backtest-methodology-reviewer` (PIT: cluster known = latest filing; routine classification correctness; small-cap proxy honesty). Address findings.

8. `Commit: \`feat(signals): opportunistic, cluster, and small-cap insider filters\``

---

## Task 6: Signal persistence — SignalStore (SQLite)  **[methodology-review]**

**Files:**
- Create: `src/signal_trader/store/signal_store.py`
- Create: `tests/store/__init__.py` if missing (already exists)
- Test: `tests/store/test_signal_store.py`

**Steps:**

1. Write failing test `tests/store/test_signal_store.py`:
```python
import datetime as dt
import json

from signal_trader.store.signal_store import SignalRecord, SignalStore


def _rec(**over):
    base = dict(
        ticker="AAPL", source="insider_form4", signal_type="open_market_purchase",
        direction="long",
        timestamp_event=dt.date(2024, 1, 10),
        timestamp_known=dt.date(2024, 1, 12),
        price_at_known=150.0,
        raw_payload={"accession_no": "a", "shares": 1000.0},
        confidence=0.7,
    )
    base.update(over)
    return SignalRecord(**base)


def test_insert_then_read_roundtrip(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec()])
    rows = store.read_signals(source="insider_form4")
    assert len(rows) == 1
    r = rows[0]
    assert r.ticker == "AAPL"
    assert r.timestamp_known == dt.date(2024, 1, 12)
    assert r.price_at_known == 150.0
    assert json.loads(r.raw_payload_json)["shares"] == 1000.0


def test_dedup_on_source_ticker_known_accession(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec(), _rec()])  # identical -> one row
    assert len(store.read_signals(source="insider_form4")) == 1


def test_read_filters_by_known_date_window(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([
        _rec(timestamp_known=dt.date(2024, 1, 12),
             raw_payload={"accession_no": "a"}),
        _rec(timestamp_known=dt.date(2024, 6, 1),
             raw_payload={"accession_no": "b"}),
    ])
    rows = store.read_signals(source="insider_form4", end="2024-02-01")
    assert len(rows) == 1
    assert rows[0].timestamp_known == dt.date(2024, 1, 12)


def test_price_at_known_may_be_none_when_no_bar(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec(price_at_known=None,
                               raw_payload={"accession_no": "c"})])
    assert store.read_signals(source="insider_form4")[0].price_at_known is None
```

2. Run → expect FAIL (module missing).

3. Implement `src/signal_trader/store/signal_store.py`:
```python
"""SQLite persistence for the Signal datamodel (Spec §9).

Mirrors PriceBarStore's pattern. Every signal carries timestamp_event (when
it happened) AND timestamp_known (when an outsider could act on it) plus the
price at the known date — the point-in-time anchor for forward returns. Dedup
key is (source, ticker, timestamp_known, accession_no) so re-ingesting the same
filings is idempotent. raw_payload is stored as JSON for auditability.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    source          TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    direction       TEXT NOT NULL,
    timestamp_event TEXT NOT NULL,
    timestamp_known TEXT NOT NULL,
    price_at_known  REAL,
    raw_payload     TEXT NOT NULL,
    confidence      REAL NOT NULL,
    accession_no    TEXT NOT NULL,
    PRIMARY KEY (source, ticker, timestamp_known, accession_no)
);
"""


@dataclass(frozen=True)
class SignalRecord:
    ticker: str
    source: str
    signal_type: str
    direction: str
    timestamp_event: dt.date
    timestamp_known: dt.date
    price_at_known: float | None
    raw_payload: dict
    confidence: float

    @property
    def accession_no(self) -> str:
        return str(self.raw_payload.get("accession_no", ""))


@dataclass(frozen=True)
class StoredSignal:
    ticker: str
    source: str
    signal_type: str
    direction: str
    timestamp_event: dt.date
    timestamp_known: dt.date
    price_at_known: float | None
    raw_payload_json: str
    confidence: float


class SignalStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def insert_signals(self, records: list[SignalRecord]) -> None:
        if not records:
            return
        rows = [
            (
                r.source, r.ticker, r.signal_type, r.direction,
                r.timestamp_event.isoformat(), r.timestamp_known.isoformat(),
                r.price_at_known, json.dumps(r.raw_payload, sort_keys=True),
                r.confidence, r.accession_no,
            )
            for r in records
        ]
        with self._connect() as con:
            con.executemany(
                "INSERT OR IGNORE INTO signals "
                "(source, ticker, signal_type, direction, timestamp_event, "
                "timestamp_known, price_at_known, raw_payload, confidence, "
                "accession_no) VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

    def read_signals(
        self,
        source: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[StoredSignal]:
        query = (
            "SELECT ticker, source, signal_type, direction, timestamp_event, "
            "timestamp_known, price_at_known, raw_payload, confidence "
            "FROM signals WHERE source = ?"
        )
        params: list[object] = [source]
        if start is not None:
            query += " AND timestamp_known >= ?"
            params.append(start)
        if end is not None:
            query += " AND timestamp_known <= ?"
            params.append(end)
        query += " ORDER BY timestamp_known, ticker"
        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
        return [
            StoredSignal(
                ticker=row[0], source=row[1], signal_type=row[2], direction=row[3],
                timestamp_event=dt.date.fromisoformat(row[4]),
                timestamp_known=dt.date.fromisoformat(row[5]),
                price_at_known=row[6],
                raw_payload_json=row[7],
                confidence=row[8],
            )
            for row in rows
        ]
```

4. Run `uv run pytest tests/store/test_signal_store.py -q` → expect PASS. `uv run ruff check .` → clean.

5. Dispatch `backtest-methodology-reviewer` (PIT: known stored and used for filtering; dedup correctness; no silent overwrite). Address findings.

6. `Commit: \`feat(store): SQLite SignalStore with point-in-time signal records\``

---

## Task 7: Pipeline — observations to persisted signals (price_at_known from bar-cache)  **[methodology-review]**

**Files:**
- Create: `src/signal_trader/signals/insider/pipeline.py`
- Test: `tests/signals/insider/test_pipeline.py`

**Steps:**

1. Write failing test `tests/signals/insider/test_pipeline.py`. It uses a fake `InsiderSource`, an in-memory price lookup, and `SignalStore` on `tmp_path`:
```python
import datetime as dt

import pandas as pd

from signal_trader.signals.insider.pipeline import build_insider_signals
from signal_trader.sources.insider_source import InsiderObservation
from signal_trader.store.signal_store import SignalStore


class FakeSource:
    def __init__(self, obs):
        self._obs = obs
    def fetch(self, tickers, start, end):
        return [o for o in self._obs if o.ticker in tickers]


def _obs(owner, ticker, day, code="P", acq="A", plan=False, price=10.0):
    return InsiderObservation(
        ticker=ticker, reporting_owner=owner, role="Director",
        transaction_code=code, acquired_disposed=acq, shares=100.0, price=price,
        timestamp_event=dt.date(2024, 1, day),
        timestamp_known=dt.date(2024, 1, day + 2),
        is_10b5_1=plan, accession_no=f"{owner}-{day}",
    )


def _close_lookup():
    # ticker -> Series of close indexed by date
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    return {"AAPL": pd.Series(range(100, 160), index=idx, dtype=float)}


def test_pipeline_keeps_only_clustered_purchases_and_prices_them(tmp_path):
    source = FakeSource([
        _obs("A", "AAPL", 1), _obs("B", "AAPL", 2), _obs("C", "AAPL", 3),
        _obs("D", "AAPL", 4, code="S"),  # sale -> dropped
        _obs("E", "AAPL", 5, plan=True),  # 10b5-1 -> dropped
    ])
    store = SignalStore(tmp_path / "t.sqlite")
    n = build_insider_signals(
        source, ["AAPL"], "2024-01-01", "2024-01-31",
        close_lookup=_close_lookup(), store=store,
        window_days=10, min_insiders=3,
    )
    rows = store.read_signals(source="insider_form4")
    assert n == len(rows) >= 1
    r = rows[0]
    assert r.direction == "long"
    assert r.signal_type == "insider_cluster_purchase"
    # price_at_known taken from the bar on/just before timestamp_known
    assert r.price_at_known is not None


def test_no_signal_when_below_cluster_threshold(tmp_path):
    source = FakeSource([_obs("A", "AAPL", 1), _obs("B", "AAPL", 2)])
    store = SignalStore(tmp_path / "t.sqlite")
    n = build_insider_signals(
        source, ["AAPL"], "2024-01-01", "2024-01-31",
        close_lookup=_close_lookup(), store=store,
        window_days=10, min_insiders=3,
    )
    assert n == 0
    assert store.read_signals(source="insider_form4") == []


def test_price_at_known_uses_last_bar_at_or_before_known_not_future(tmp_path):
    # known is a weekend/gap day -> must use prior bar, never a later one
    source = FakeSource([_obs("A", "AAPL", 1), _obs("B", "AAPL", 2), _obs("C", "AAPL", 3)])
    store = SignalStore(tmp_path / "t.sqlite")
    build_insider_signals(
        source, ["AAPL"], "2024-01-01", "2024-01-31",
        close_lookup=_close_lookup(), store=store, window_days=10, min_insiders=3,
    )
    r = store.read_signals(source="insider_form4")[0]
    known_idx = pd.Timestamp(r.timestamp_known)
    series = _close_lookup()["AAPL"]
    expected = float(series.loc[:known_idx].iloc[-1])
    assert r.price_at_known == expected
```

2. Run → expect FAIL (module missing).

3. Implement `src/signal_trader/signals/insider/pipeline.py`:
```python
"""Compose source -> filters -> cluster -> priced, persisted signals.

Point-in-time end to end: price_at_known is the close on the last bar AT OR
BEFORE timestamp_known (never a later bar — that would be lookahead). A cluster
becomes a signal at its latest member's filing date. confidence scales with the
number of distinct insiders (more independent buyers = stronger). Nothing about
the trade date drives the recorded known date.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from signal_trader.signals.insider.cluster import cluster_purchases
from signal_trader.signals.insider.filters import keep_open_market_purchases
from signal_trader.signals.insider.opportunistic import keep_opportunistic
from signal_trader.sources.insider_source import InsiderSource
from signal_trader.store.signal_store import SignalRecord, SignalStore

SOURCE_NAME = "insider_form4"
_SIGNAL_TYPE = "insider_cluster_purchase"


def _price_at_or_before(close: pd.Series, known: dt.date) -> float | None:
    prior = close.loc[: pd.Timestamp(known)]
    if prior.empty:
        return None
    return float(prior.iloc[-1])


def build_insider_signals(
    source: InsiderSource,
    tickers: list[str],
    start: str,
    end: str,
    close_lookup: dict[str, pd.Series],
    store: SignalStore,
    window_days: int = 10,
    min_insiders: int = 3,
) -> int:
    """Fetch, filter, cluster, price, and persist insider signals. Returns count."""
    observations = source.fetch(tickers, start, end)
    purchases = keep_opportunistic(keep_open_market_purchases(observations))
    clusters = cluster_purchases(
        purchases, window_days=window_days, min_insiders=min_insiders
    )
    records: list[SignalRecord] = []
    for cluster in clusters:
        close = close_lookup.get(cluster.ticker)
        price = (
            _price_at_or_before(close, cluster.timestamp_known)
            if close is not None
            else None
        )
        earliest_event = min(m.timestamp_event for m in cluster.members)
        records.append(
            SignalRecord(
                ticker=cluster.ticker,
                source=SOURCE_NAME,
                signal_type=_SIGNAL_TYPE,
                direction="long",
                timestamp_event=earliest_event,
                timestamp_known=cluster.timestamp_known,
                price_at_known=price,
                raw_payload={
                    "accession_no": cluster.members[-1].accession_no,
                    "n_insiders": cluster.n_insiders,
                    "owners": sorted({m.reporting_owner for m in cluster.members}),
                },
                confidence=min(1.0, cluster.n_insiders / 5.0),
            )
        )
    store.insert_signals(records)
    return len(records)
```

4. Run `uv run pytest tests/signals/insider/test_pipeline.py -q` → expect PASS. `uv run ruff check .` → clean.

5. Dispatch `backtest-methodology-reviewer` (PIT: price_at_known never uses a future bar; cluster known propagated; no leakage). Address findings.

6. `Commit: \`feat(signals): insider pipeline persisting point-in-time clustered signals\``

---

## Task 8: Forward return per signal (from the bar-cache, anchored at known)

**Files:**
- Create: `src/signal_trader/signals/scoring/__init__.py` (empty)
- Create: `src/signal_trader/signals/scoring/forward_return.py`
- Create: `tests/signals/scoring/__init__.py` (empty)
- Test: `tests/signals/scoring/test_forward_return.py`

**Steps:**

1. Write failing test `tests/signals/scoring/test_forward_return.py`:
```python
import datetime as dt

import pandas as pd

from signal_trader.signals.scoring.forward_return import forward_return


def _close():
    idx = pd.date_range("2024-01-01", periods=40, freq="B")
    return pd.Series([100.0 + i for i in range(40)], index=idx)


def test_forward_return_is_entry_to_horizon_close():
    close = _close()
    known = dt.date(2024, 1, 1)
    # entry on FIRST bar strictly after known; return over `horizon` bars
    fr = forward_return(close, known, horizon=5)
    bars = close.loc[pd.Timestamp(known):]
    entry = bars.iloc[1]          # bar after known (PIT)
    exit_ = bars.iloc[1 + 5]
    assert abs(fr - (exit_ / entry - 1.0)) < 1e-9


def test_returns_none_when_not_enough_forward_bars():
    close = _close()
    known = close.index[-2].date()
    assert forward_return(close, known, horizon=10) is None


def test_entry_is_strictly_after_known_no_same_bar_fill():
    close = _close()
    known = close.index[0].date()
    fr = forward_return(close, known, horizon=1)
    entry = close.iloc[1]
    exit_ = close.iloc[2]
    assert abs(fr - (exit_ / entry - 1.0)) < 1e-9
```

2. Run → expect FAIL (module missing).

3. Implement `src/signal_trader/signals/scoring/forward_return.py`:
```python
"""Forward return of a signal, anchored point-in-time at timestamp_known.

Entry is the FIRST bar STRICTLY AFTER timestamp_known (an outsider learns of
the filing on the known date and can only trade the next session), and the
exit is `horizon` bars later. Returns None when the cache lacks enough forward
bars — we never truncate the horizon silently to manufacture a number.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd


def forward_return(
    close: pd.Series, timestamp_known: dt.date, horizon: int = 5
) -> float | None:
    """Return over `horizon` bars from the bar after `timestamp_known`."""
    after = close.loc[close.index > pd.Timestamp(timestamp_known)]
    if len(after) < horizon + 1:
        return None
    entry = float(after.iloc[0])
    exit_ = float(after.iloc[horizon])
    if entry == 0:
        return None
    return exit_ / entry - 1.0
```

4. Run `uv run pytest tests/signals/scoring/test_forward_return.py -q` → expect PASS. `uv run ruff check .` → clean.

5. `Commit: \`feat(scoring): point-in-time forward return per signal\``

---

## Task 9: SourceScore — hit-rate, avg forward return, data-lag  **[methodology-review]**

**Files:**
- Create: `src/signal_trader/signals/scoring/source_score.py`
- Create: `src/signal_trader/store/signal_store.py` (extend with SourceScore persistence)
- Test: `tests/signals/scoring/test_source_score.py`
- Test: `tests/store/test_signal_store.py` (extend)

**Steps:**

1. Extend `tests/store/test_signal_store.py` with SourceScore persistence:
```python
def test_source_score_upsert_and_read(tmp_path):
    from signal_trader.store.signal_store import SourceScoreRecord, SignalStore
    store = SignalStore(tmp_path / "t.sqlite")
    store.upsert_source_score(SourceScoreRecord(
        source="insider_form4", window="5d", n_signals=10,
        hit_rate=0.6, avg_forward_return=0.012, avg_data_lag_days=2.5,
    ))
    store.upsert_source_score(SourceScoreRecord(
        source="insider_form4", window="5d", n_signals=12,
        hit_rate=0.5, avg_forward_return=0.009, avg_data_lag_days=2.7,
    ))  # same (source, window) -> replace
    scores = store.read_source_scores()
    assert len(scores) == 1
    assert scores[0].n_signals == 12
    assert scores[0].avg_data_lag_days == 2.7
```

2. Run → expect FAIL. Extend `src/signal_trader/store/signal_store.py`: add the table to `_SCHEMA` (append, keep the existing `signals` DDL) and the dataclass + methods:
```python
# --- append to _SCHEMA string ---
CREATE TABLE IF NOT EXISTS source_scores (
    source             TEXT NOT NULL,
    window             TEXT NOT NULL,
    n_signals          INTEGER NOT NULL,
    hit_rate           REAL NOT NULL,
    avg_forward_return REAL NOT NULL,
    avg_data_lag_days  REAL NOT NULL,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (source, window)
);
```
```python
@dataclass(frozen=True)
class SourceScoreRecord:
    source: str
    window: str
    n_signals: int
    hit_rate: float
    avg_forward_return: float
    avg_data_lag_days: float


# --- methods on SignalStore ---
    def upsert_source_score(self, record: SourceScoreRecord) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO source_scores "
                "(source, window, n_signals, hit_rate, avg_forward_return, "
                "avg_data_lag_days) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source, window) DO UPDATE SET "
                "n_signals=excluded.n_signals, hit_rate=excluded.hit_rate, "
                "avg_forward_return=excluded.avg_forward_return, "
                "avg_data_lag_days=excluded.avg_data_lag_days, "
                "updated_at=datetime('now')",
                (
                    record.source, record.window, record.n_signals,
                    record.hit_rate, record.avg_forward_return,
                    record.avg_data_lag_days,
                ),
            )

    def read_source_scores(self) -> list[SourceScoreRecord]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT source, window, n_signals, hit_rate, avg_forward_return, "
                "avg_data_lag_days FROM source_scores ORDER BY source, window"
            ).fetchall()
        return [
            SourceScoreRecord(
                source=r[0], window=r[1], n_signals=r[2], hit_rate=r[3],
                avg_forward_return=r[4], avg_data_lag_days=r[5],
            )
            for r in rows
        ]
```

3. Run `uv run pytest tests/store/test_signal_store.py -q` → expect PASS.

4. Write failing test `tests/signals/scoring/test_source_score.py`:
```python
import datetime as dt

import pandas as pd

from signal_trader.signals.scoring.source_score import score_source
from signal_trader.store.signal_store import SignalRecord, SignalStore


def _close_lookup():
    idx = pd.date_range("2024-01-01", periods=60, freq="B")
    up = pd.Series([100.0 + i for i in range(60)], index=idx)     # always up
    return {"WIN": up, "LOSE": up.iloc[::-1].reset_index(drop=True).set_axis(idx)}


def _rec(ticker, known, event, source="insider_form4"):
    return SignalRecord(
        ticker=ticker, source=source, signal_type="insider_cluster_purchase",
        direction="long", timestamp_event=event, timestamp_known=known,
        price_at_known=100.0, raw_payload={"accession_no": f"{ticker}-{known}"},
        confidence=0.5,
    )


def test_hit_rate_and_avg_return_and_lag(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([
        _rec("WIN", dt.date(2024, 1, 2), dt.date(2024, 1, 1)),   # +2 day lag, up -> hit
        _rec("LOSE", dt.date(2024, 1, 5), dt.date(2024, 1, 2)),  # +3 day lag, down -> miss
    ])
    score = score_source(
        store, source="insider_form4", close_lookup=_close_lookup(),
        horizon=5, window_label="5d",
    )
    assert score.n_signals == 2
    assert 0.0 <= score.hit_rate <= 1.0
    assert score.hit_rate == 0.5
    assert score.avg_data_lag_days == 2.5  # (1 + 4)/2 trade->filing days


def test_signals_without_enough_forward_bars_are_excluded_not_counted_as_miss(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    store.insert_signals([_rec("WIN", dt.date(2024, 3, 25), dt.date(2024, 3, 22))])
    score = score_source(
        store, source="insider_form4", close_lookup=_close_lookup(),
        horizon=200, window_label="200d",
    )
    assert score.n_signals == 0  # no scoreable signal, not a fake miss
```

5. Run → expect FAIL. Implement `src/signal_trader/signals/scoring/source_score.py`:
```python
"""Per-source hit-rate, avg forward return, and DATA LAG (Acceptance §3, §4).

Hit-rate and avg forward return are computed only over signals with enough
forward bars in the cache — a signal we cannot score is EXCLUDED, never counted
as a miss (that would manufacture pessimism the same way silent truncation
manufactures optimism). Data lag = mean(timestamp_known - timestamp_event) in
days, making each source's reporting delay explicit in the system.
"""
from __future__ import annotations

import pandas as pd

from signal_trader.signals.scoring.forward_return import forward_return
from signal_trader.store.signal_store import SignalStore, SourceScoreRecord


def score_source(
    store: SignalStore,
    source: str,
    close_lookup: dict[str, pd.Series],
    horizon: int = 5,
    window_label: str = "5d",
    persist: bool = False,
) -> SourceScoreRecord:
    """Compute (and optionally persist) the SourceScore for one source."""
    signals = store.read_signals(source=source)
    returns: list[float] = []
    lags: list[int] = []
    for sig in signals:
        lags.append((sig.timestamp_known - sig.timestamp_event).days)
        close = close_lookup.get(sig.ticker)
        if close is None:
            continue
        fr = forward_return(close, sig.timestamp_known, horizon=horizon)
        if fr is not None:
            returns.append(fr)
    n = len(returns)
    hit_rate = sum(1 for r in returns if r > 0) / n if n else 0.0
    avg_ret = sum(returns) / n if n else 0.0
    avg_lag = sum(lags) / len(lags) if lags else 0.0
    record = SourceScoreRecord(
        source=source, window=window_label, n_signals=n,
        hit_rate=hit_rate, avg_forward_return=avg_ret, avg_data_lag_days=avg_lag,
    )
    if persist:
        store.upsert_source_score(record)
    return record
```

6. Run `uv run pytest tests/signals/scoring/test_source_score.py -q` → expect PASS. `uv run ruff check .` → clean.

7. Dispatch `backtest-methodology-reviewer` (unscoreable signals excluded not faked; data-lag from known−event; no truncation). Address findings.

8. `Commit: \`feat(scoring): per-source hit-rate, forward return, and data lag\``

---

## Task 10: Consolidation + InsiderStrategy (PIT entries/exits)  **[methodology-review]**

**Files:**
- Create: `src/signal_trader/signals/consolidate/__init__.py` (empty)
- Create: `src/signal_trader/signals/consolidate/consolidate.py`
- Create: `src/signal_trader/strategy/longterm/__init__.py` (empty)
- Create: `src/signal_trader/strategy/longterm/insider_strategy.py`
- Create: `tests/signals/consolidate/__init__.py`, `tests/strategy/__init__.py`, `tests/strategy/longterm/__init__.py` (empty)
- Test: `tests/signals/consolidate/test_consolidate.py`
- Test: `tests/strategy/longterm/test_insider_strategy.py`

**Steps:**

1. Write failing test `tests/signals/consolidate/test_consolidate.py`:
```python
import datetime as dt

from signal_trader.signals.consolidate.consolidate import consolidate_per_ticker
from signal_trader.store.signal_store import StoredSignal


def _sig(ticker, known, conf):
    return StoredSignal(
        ticker=ticker, source="insider_form4", signal_type="insider_cluster_purchase",
        direction="long", timestamp_event=dt.date(2024, 1, 1),
        timestamp_known=known, price_at_known=100.0,
        raw_payload_json="{}", confidence=conf,
    )


def test_consolidated_score_sums_contributing_confidence():
    sigs = [_sig("AAPL", dt.date(2024, 1, 2), 0.4), _sig("AAPL", dt.date(2024, 1, 5), 0.6)]
    out = consolidate_per_ticker(sigs)
    assert out["AAPL"].consolidated_score == 1.0
    assert out["AAPL"].n_contributing == 2
    assert out["AAPL"].latest_known == dt.date(2024, 1, 5)


def test_separate_tickers_kept_apart():
    out = consolidate_per_ticker([_sig("AAPL", dt.date(2024, 1, 2), 0.4),
                                  _sig("MSFT", dt.date(2024, 1, 2), 0.7)])
    assert set(out) == {"AAPL", "MSFT"}
```

2. Run → expect FAIL. Implement `src/signal_trader/signals/consolidate/consolidate.py`:
```python
"""Per-ticker consolidation of contributing signals (Spec §9 Suggestion).

consolidated_score = sum of contributing signal confidences; latest_known is
the most recent point-in-time date among contributors (the earliest an outsider
could act on the consolidated view). Pure aggregation, no price lookups.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from signal_trader.store.signal_store import StoredSignal


@dataclass(frozen=True)
class ConsolidatedSignal:
    ticker: str
    consolidated_score: float
    n_contributing: int
    latest_known: dt.date


def consolidate_per_ticker(
    signals: list[StoredSignal],
) -> dict[str, ConsolidatedSignal]:
    by_ticker: dict[str, list[StoredSignal]] = {}
    for s in signals:
        by_ticker.setdefault(s.ticker, []).append(s)
    out: dict[str, ConsolidatedSignal] = {}
    for ticker, group in by_ticker.items():
        out[ticker] = ConsolidatedSignal(
            ticker=ticker,
            consolidated_score=sum(s.confidence for s in group),
            n_contributing=len(group),
            latest_known=max(s.timestamp_known for s in group),
        )
    return out
```

3. Run `uv run pytest tests/signals/consolidate/test_consolidate.py -q` → expect PASS.

4. Write failing test `tests/strategy/longterm/test_insider_strategy.py`:
```python
import datetime as dt

import pandas as pd

from signal_trader.strategy.longterm.insider_strategy import insider_entries_exits
from signal_trader.store.signal_store import StoredSignal


def _sig(known):
    return StoredSignal(
        ticker="AAPL", source="insider_form4", signal_type="insider_cluster_purchase",
        direction="long", timestamp_event=dt.date(2024, 1, 1),
        timestamp_known=known, price_at_known=100.0, raw_payload_json="{}",
        confidence=0.6,
    )


def _close():
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    return pd.Series([100.0 + i for i in range(30)], index=idx)


def test_entry_fires_on_bar_strictly_after_known():
    close = _close()
    known = close.index[3].date()
    entries, exits = insider_entries_exits(close, [_sig(known)], hold_bars=5)
    assert not entries.iloc[:4].any()           # nothing on/before known bar
    assert bool(entries.iloc[4])                # first bar AFTER known
    assert len(entries) == len(close)


def test_exit_fires_hold_bars_after_entry():
    close = _close()
    known = close.index[3].date()
    entries, exits = insider_entries_exits(close, [_sig(known)], hold_bars=5)
    assert bool(exits.iloc[4 + 5])


def test_no_entries_without_signals():
    close = _close()
    entries, exits = insider_entries_exits(close, [], hold_bars=5)
    assert not entries.any() and not exits.any()


def test_signal_known_after_data_window_produces_no_entry():
    close = _close()
    entries, exits = insider_entries_exits(close, [_sig(dt.date(2025, 1, 1))], hold_bars=5)
    assert not entries.any()
```

5. Run → expect FAIL. Implement `src/signal_trader/strategy/longterm/insider_strategy.py`:
```python
"""Insider long-term strategy: consolidated signals -> PIT entries/exits.

Both Phase-1 engines consume boolean entries/exits aligned to the close index.
Point-in-time: an entry fires on the FIRST bar STRICTLY AFTER timestamp_known
(the filing is public only from the known date; the earliest tradable bar is
the next session). Exit fires `hold_bars` bars after entry — a fixed holding
period, the simplest rule that exercises the harness. No same-bar fills, so the
Phase-1 shift-test stays meaningful.
"""
from __future__ import annotations

import pandas as pd

from signal_trader.store.signal_store import StoredSignal


def insider_entries_exits(
    close: pd.Series,
    signals: list[StoredSignal],
    hold_bars: int = 5,
) -> tuple[pd.Series, pd.Series]:
    """Boolean (entries, exits) aligned to `close` for the given signals."""
    entries = pd.Series(False, index=close.index)
    exits = pd.Series(False, index=close.index)
    for sig in signals:
        after = close.index[close.index > pd.Timestamp(sig.timestamp_known)]
        if len(after) == 0:
            continue
        entry_ts = after[0]
        entry_pos = close.index.get_loc(entry_ts)
        entries.iloc[entry_pos] = True
        exit_pos = entry_pos + hold_bars
        if exit_pos < len(close):
            exits.iloc[exit_pos] = True
    return entries, exits
```

6. Run `uv run pytest tests/strategy/longterm/test_insider_strategy.py -q` → expect PASS. `uv run ruff check .` → clean.

7. Dispatch `backtest-methodology-reviewer` (PIT: entry strictly after known, no same-bar lookahead; exits inside the window). Address findings.

8. `Commit: \`feat(strategy): consolidation and point-in-time insider entries/exits\``

---

## Task 11: Insider strategy through BOTH engines + shift/OOS/walk-forward  **[methodology-review]**

Reuses the Phase-1 engines and validation modules unchanged.

**Files:**
- Test: `tests/strategy/longterm/test_insider_engine_run.py`

(No new production module: the engines, costs, benchmark, metrics, and validation already exist. This task proves the insider entries/exits run through both engines and pass the leakage discipline; any minimal helper needed lives in `insider_strategy.py`.)

**Steps:**

1. Write failing test `tests/strategy/longterm/test_insider_engine_run.py`. It builds entries/exits from the strategy, then drives BOTH engines exactly as the foundation report does, asserts trade-count parity and after-cost equity, and runs the Phase-1 shift-test on the insider position series. Because both engines hard-code the momentum signal internally, add a thin run helper `run_insider_through_engines(close, signals, cost_model, hold_bars)` to `insider_strategy.py` that builds a vectorbt portfolio from the strategy's entries/exits via `vbt.Portfolio.from_signals` and a `BacktestResult`, plus an event-driven run via a `backtesting.py` Strategy constructed from the precomputed entries/exits:
```python
import datetime as dt

import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.validation import shift_test
from signal_trader.store.signal_store import StoredSignal
from signal_trader.strategy.longterm.insider_strategy import (
    insider_entries_exits,
    run_insider_through_engines,
)

_COST = CostModel(commission_per_trade=0.001, slippage=0.0005)


def _close():
    idx = pd.date_range("2024-01-01", periods=120, freq="B")
    return pd.Series([100.0 + i * 0.5 for i in range(120)], index=idx)


def _signals(close):
    return [
        StoredSignal(
            ticker="AAPL", source="insider_form4",
            signal_type="insider_cluster_purchase", direction="long",
            timestamp_event=dt.date(2024, 1, 1),
            timestamp_known=close.index[d].date(), price_at_known=100.0,
            raw_payload_json="{}", confidence=0.6,
        )
        for d in (10, 40, 70)
    ]


def test_both_engines_run_and_agree_on_trade_count():
    close = _close()
    results = run_insider_through_engines(close, _signals(close), _COST, hold_bars=5)
    assert set(results) == {"vectorbt", "backtesting.py"}
    assert results["vectorbt"].n_trades == results["backtesting.py"].n_trades
    assert (results["vectorbt"].equity_curve > 0).all()


def test_insider_position_series_passes_shift_test():
    close = _close()
    entries, exits = insider_entries_exits(close, _signals(close), hold_bars=5)
    position = entries.astype(float)  # 1 on entry bar (already known+1, PIT-safe)
    returns = close.pct_change().fillna(0.0)
    result = shift_test(position, returns)
    assert result["collapsed"] is False  # PIT signal survives the extra lag
```

2. Run → expect FAIL (`run_insider_through_engines` missing).

3. Add to `src/signal_trader/strategy/longterm/insider_strategy.py`:
```python
import vectorbt as vbt
from backtesting import Backtest, Strategy

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.result import BacktestResult

_INIT_CASH = 10_000


def _make_signal_strategy(entries: pd.Series, exits: pd.Series) -> type[Strategy]:
    class _Signal(Strategy):
        def init(self):
            self.entries = self.I(lambda: entries.to_numpy(), name="entries")
            self.exits = self.I(lambda: exits.to_numpy(), name="exits")

        def next(self):
            if self.entries[-1] and not self.position:
                self.buy()
            elif self.exits[-1] and self.position:
                self.position.close()

    return _Signal


def run_insider_through_engines(
    close: pd.Series,
    signals: list[StoredSignal],
    cost_model: CostModel,
    hold_bars: int = 5,
) -> dict[str, BacktestResult]:
    """Run the insider entries/exits through BOTH Phase-1 engines after costs."""
    entries, exits = insider_entries_exits(close, signals, hold_bars=hold_bars)

    pf = vbt.Portfolio.from_signals(
        close=close, entries=entries, exits=exits, init_cash=_INIT_CASH,
        fees=cost_model.commission_per_trade, slippage=cost_model.slippage,
        freq="1D",
    )
    vbt_equity = pf.value()
    vbt_equity.index = pd.DatetimeIndex(close.index)
    vbt_result = BacktestResult(
        engine="vectorbt", equity_curve=vbt_equity, n_trades=int(pf.trades.count())
    )

    ohlcv = pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close,
         "Volume": 1_000_000.0}
    )
    bt = Backtest(
        ohlcv, _make_signal_strategy(entries, exits), cash=_INIT_CASH,
        commission=cost_model.commission_per_trade, spread=cost_model.slippage,
        finalize_trades=True,
    )
    stats = bt.run()
    bt_equity = stats["_equity_curve"]["Equity"]
    bt_equity.index = pd.DatetimeIndex(ohlcv.index)
    bt_result = BacktestResult(
        engine="backtesting.py", equity_curve=bt_equity,
        n_trades=int(stats["# Trades"]),
    )
    return {"vectorbt": vbt_result, "backtesting.py": bt_result}
```

4. Run `uv run pytest tests/strategy/longterm/test_insider_engine_run.py -q` → expect PASS. `uv run ruff check .` → clean.

5. Dispatch `backtest-methodology-reviewer` (both engines after costs; shift-test on PIT position does NOT collapse; trade-count parity; benchmark discipline carried into Task 12). Address findings.

6. `Commit: \`feat(strategy): run insider signals through both engines with leakage check\``

---

## Task 12: CLIs — ingest, insider report (both engines + hit-rates + benchmark), live SEC smoke  **[methodology-review]**

**Files:**
- Create: `scripts/ingest_insider.py`
- Create: `scripts/run_insider_report.py`
- Create: `scripts/sec_smoke.py`
- Modify: `README.md` (insider data-lag caveat)
- Test: `tests/test_insider_scripts.py`

**Steps:**

1. Write failing test `tests/test_insider_scripts.py`. It fakes the source and price cache, runs `ingest_insider.main` and `run_insider_report.main` end-to-end on `tmp_path`, and asserts the report prints both engines, the after-cost benchmark, and the hit-rate / data-lag line. `sec_smoke` is NOT exercised in pytest (it would hit the network); only its import is asserted safe:
```python
import datetime as dt
import sys
from unittest.mock import patch

import pandas as pd

import scripts.ingest_insider as ingest
import scripts.run_insider_report as report
from signal_trader.sources.insider_source import InsiderObservation


class FakeSource:
    def __init__(self, *a, **k):
        pass
    def fetch(self, tickers, start, end):
        out = []
        for owner, day in [("A", 3), ("B", 4), ("C", 5)]:
            out.append(InsiderObservation(
                ticker="AAPL", reporting_owner=owner, role="Director",
                transaction_code="P", acquired_disposed="A", shares=100.0, price=10.0,
                timestamp_event=dt.date(2024, 1, day),
                timestamp_known=dt.date(2024, 1, day + 1),
                is_10b5_1=False, accession_no=f"{owner}-{day}",
            ))
        return out


def _fake_close_lookup(tickers, start, end):
    idx = pd.date_range("2024-01-01", periods=120, freq="B")
    return {"AAPL": pd.Series([100.0 + i for i in range(120)], index=idx)}


def test_ingest_then_report_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ingest, "EdgarForm4Source", FakeSource)
    monkeypatch.setattr(ingest.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(ingest, "_load_close_lookup", _fake_close_lookup)
    monkeypatch.setattr(ingest.config, "sec_identity", lambda: "X y@z.com")
    with patch.object(sys, "argv",
                      ["ingest_insider.py", "--tickers", "AAPL",
                       "--start", "2024-01-01", "--end", "2024-01-31"]):
        ingest.main()

    monkeypatch.setattr(report.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(report, "_load_close_lookup", _fake_close_lookup)
    with patch.object(sys, "argv",
                      ["run_insider_report.py", "--tickers", "AAPL",
                       "--start", "2024-01-01", "--end", "2024-06-30"]):
        report.main()
    out = capsys.readouterr().out
    assert "Insider Report" in out
    assert "vectorbt" in out and "backtesting.py" in out
    assert "Buy & Hold (after costs)" in out
    assert "hit_rate" in out and "data_lag" in out


def test_sec_smoke_importable_without_network():
    import scripts.sec_smoke as smoke  # noqa: F401
```

2. Run → expect FAIL (modules missing).

3. Implement `scripts/ingest_insider.py`:
```python
"""CLI: ingest Form 4 -> filter -> persist insider signals (point-in-time).

    uv run python scripts/ingest_insider.py --tickers AAPL MSFT \
        --start 2024-01-01 --end 2024-12-31

EdgarForm4Source is faked in tests; the only live SEC contact is sec_smoke.py.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.signals.insider.pipeline import build_insider_signals
from signal_trader.sources.edgar_form4 import EdgarForm4Source
from signal_trader.store.cache_service import CacheService
from signal_trader.store.signal_store import SignalStore


def _load_close_lookup(
    tickers: list[str], start: str, end: str
) -> dict[str, pd.Series]:
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill(tickers, start, end)
    wide = service.load_close_matrix(tickers, start, end)
    return {t: wide[t].dropna() for t in tickers}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest insider Form 4 signals")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--min-insiders", type=int, default=3)
    args = parser.parse_args()

    source = EdgarForm4Source(identity=config.sec_identity())
    close_lookup = _load_close_lookup(args.tickers, args.start, args.end)
    store = SignalStore(config.SQLITE_PATH)
    n = build_insider_signals(
        source, args.tickers, args.start, args.end,
        close_lookup=close_lookup, store=store,
        window_days=args.window_days, min_insiders=args.min_insiders,
    )
    print(f"Persisted {n} insider signal(s) into {config.SQLITE_PATH}")


if __name__ == "__main__":
    main()
```

4. Implement `scripts/run_insider_report.py`:
```python
"""CLI: insider strategy through BOTH engines + hit-rates + after-cost benchmark.

    uv run python scripts/run_insider_report.py --tickers AAPL \
        --start 2024-01-01 --end 2024-12-31

Every figure is after costs; the benchmark is buy-and-hold after the SAME costs;
each source's hit-rate AND data-lag are printed (Acceptance §3, §4). Reuses the
Phase-1 engines, cost model, benchmark, and metrics unchanged.
"""
from __future__ import annotations

import argparse

import pandas as pd

from signal_trader import config
from signal_trader.backtest.benchmark import buy_and_hold_equity
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.metrics import compute_metrics
from signal_trader.market_data.provider import YFinanceProvider
from signal_trader.signals.scoring.source_score import score_source
from signal_trader.store.cache_service import CacheService
from signal_trader.store.signal_store import SignalStore
from signal_trader.strategy.longterm.insider_strategy import run_insider_through_engines

SOURCE_NAME = "insider_form4"


def _load_close_lookup(
    tickers: list[str], start: str, end: str
) -> dict[str, pd.Series]:
    service = CacheService(YFinanceProvider(), config.PARQUET_DIR, config.SQLITE_PATH)
    service.backfill(tickers, start, end)
    wide = service.load_close_matrix(tickers, start, end)
    return {t: wide[t].dropna() for t in tickers}


def main() -> None:
    parser = argparse.ArgumentParser(description="Insider strategy report")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--hold-bars", type=int, default=5)
    parser.add_argument("--horizon", type=int, default=5)
    args = parser.parse_args()

    cost_model = CostModel(
        commission_per_trade=args.commission, slippage=args.slippage
    )
    close_lookup = _load_close_lookup(args.tickers, args.start, args.end)
    store = SignalStore(config.SQLITE_PATH)
    signals = store.read_signals(source=SOURCE_NAME, start=args.start, end=args.end)

    lines = ["=== Insider Report (all figures after costs) ===", ""]
    for ticker in args.tickers:
        close = close_lookup[ticker]
        ticker_signals = [s for s in signals if s.ticker == ticker]
        results = run_insider_through_engines(
            close, ticker_signals, cost_model, hold_bars=args.hold_bars
        )
        for engine, res in results.items():
            m = compute_metrics(res.returns())
            lines.append(
                f"[{ticker}/{engine}] trades={res.n_trades} CAGR={m.cagr:.3f} "
                f"Sharpe={m.sharpe:.3f} Sortino={m.sortino:.3f} "
                f"Calmar={m.calmar:.3f} MaxDD={m.max_drawdown:.3f} PSR={m.psr:.3f}"
            )
        bench = compute_metrics(
            buy_and_hold_equity(close, cost_model).pct_change().dropna()
        )
        lines.append(
            f"[{ticker}/Buy & Hold (after costs)] CAGR={bench.cagr:.3f} "
            f"Sharpe={bench.sharpe:.3f} Sortino={bench.sortino:.3f} "
            f"Calmar={bench.calmar:.3f} MaxDD={bench.max_drawdown:.3f} "
            f"PSR={bench.psr:.3f}"
        )

    score = score_source(
        store, source=SOURCE_NAME, close_lookup=close_lookup,
        horizon=args.horizon, window_label=f"{args.horizon}d", persist=True,
    )
    lines.append("")
    lines.append(
        f"[{SOURCE_NAME}] n_signals={score.n_signals} "
        f"hit_rate={score.hit_rate:.3f} "
        f"avg_forward_return={score.avg_forward_return:.4f} "
        f"data_lag_days={score.avg_data_lag_days:.2f}"
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
```

5. Implement `scripts/sec_smoke.py`:
```python
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
```

6. Append to `README.md` the insider data-lag caveat (Spec §11.4): "Insider lag — trade date + up to ~2 business days to file + polling ⇒ realistically 2–3 days behind; pre-publication alpha is unavailable. `timestamp_known` is the filing date and the only date used for trading; `timestamp_event` (trade date) is recorded for audit only."

7. Run `uv run pytest tests/test_insider_scripts.py -q` → expect PASS. Run the full suite `uv run pytest -q` → expect PASS. `uv run ruff check .` → clean.

8. Dispatch `backtest-methodology-reviewer` on the full Phase-2 diff (after-cost everywhere, benchmark after costs, PIT throughout, data-lag visible, no live call in tests). Address findings.

9. `Commit: \`feat(scripts): insider ingest, both-engine report, and live SEC smoke\``

---

## Verification before completion

Before claiming Phase 2 complete, run and confirm output (REQUIRED SUB-SKILL: `superpowers:verification-before-completion`):

1. `uv run pytest -q` — entire suite green (Phase 1 + all Phase 2 tests).
2. `uv run ruff check .` — clean.
3. Confirm NO test imports trigger a live SEC/network call: `uv run pytest -q -k insider` runs fully offline; edgartools is mocked in `tests/sources/test_edgar_form4.py` and faked in pipeline/script tests.
4. Spot-check the iron principles in the diff:
   - **Point-in-time:** `timestamp_known` = filing date everywhere; entries fire strictly after known; `price_at_known` and `forward_return` never read a future bar.
   - **Costs/benchmark:** the report runs both engines after costs and prints buy-and-hold after the same costs.
   - **Leakage:** `test_insider_position_series_passes_shift_test` shows the PIT position does NOT collapse under the shift-test.
   - **No silent truncation:** unparseable filings are logged+skipped; unscoreable signals are excluded, never counted as misses.
   - **Data-lag visible:** `avg_data_lag_days` printed and persisted in `source_scores`.
5. **Live SEC smoke (controller-only, separate run):** ensure `SEC_IDENTITY` is set in `.env`, then run `uv run python scripts/sec_smoke.py --ticker AAPL --start 2024-01-01 --end 2024-03-31` and confirm it prints real observations with `known >= event`. This is the only live network step and is run by the controller, never inside pytest.
6. Dispatch a final `backtest-methodology-reviewer` pass over the complete Phase-2 diff; resolve any findings before the phase-gate report to Nico.

Sources (edgartools API verification):
- [edgartools (PyPI) — version 5.36.0, 2026-06-09](https://pypi.org/project/edgartools/)
- [Track Insider Trading: Form 4 guide](https://edgartools.readthedocs.io/en/stable/guides/track-form4/)
- [Insider Trades (Form 4) reference — market_trades, has_10b5_1_plan, position](https://edgartools.readthedocs.io/en/stable/insider-filings/)
- [Working with Filings — get_filings filing_date range syntax](https://edgartools.readthedocs.io/en/latest/guides/working-with-filing/)
- [edgartools GitHub](https://github.com/dgunning/edgartools)
