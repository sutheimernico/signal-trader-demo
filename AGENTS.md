# Signal-Trader-Demo — Codebase Operations (AGENTS.md)

Operatives Begleitdokument zu `PROJECT.md` (Source of Truth) und `CLAUDE.md` (Arbeitsweise). Für Agents und Menschen, die im Code arbeiten.

## Agent stance
Python-zentriert. Korrektheit und Leakage-Freiheit vor Cleverness. Jede Strategie-/Backtest-Änderung ist erst fertig, wenn sie Kosten einrechnet, gegen einen Benchmark nach Kosten gemessen ist und den Shift-Test besteht. „Sieht profitabel aus" ist ein Verdacht, kein Ergebnis.

## Architecture (Layer → Code)
```
src/signal_trader/
  market_data/   Bars ziehen/normalisieren/cachen (Provider-Seam: yfinance jetzt)
  sources/       Signalquellen (EDGAR Form 4/13F — Phase 2)
  store/         Persistenz: Schema, Migrationen, Repositories (SQLite)
  signals/       insider/ · consolidate/ · scoring/ (Phase 2)
  strategy/      longterm/ (Spur 1) · shortterm/ (Spur 2, Phase 4)
  backtest/      engine/ (vectorbt + backtesting.py Adapter) · baselines/ (Momentum)
  paper/alpaca/  Paper-Trading (Stub in v1)
app/             backend/ (FastAPI) · frontend/ (React 19) — Phase 3
data/            Cache (Parquet/SQLite) — gitignored
scripts/         CLI-Einstiege (Backfill, Backtest-Run)
config/  tests/
```

## Run / Build / Test
Toolchain wird in **Phase 0** etabliert (noch kein `pyproject` committed). Geplant:
- Env/Deps: `uv` (gepinnt in `pyproject.toml` + `uv.lock`).
- Tests: `pytest` (`tests/` spiegelt `src/`); reine Logik unit-getestet, Netz-/SDK-Calls gefakt.
- Lint/Format: `ruff`.
- Backfill/Backtest: über `scripts/` (z. B. `scripts/backfill.py`, `scripts/run_backtest.py`).

## Best-first edits
- Erst lesen, dann schreiben: bestehende Muster im Repo prüfen und übernehmen.
- Datenquellen hinter Schnittstelle (Provider-Seam) — keine direkten yfinance-Calls verstreut im Code.
- Backtest-Engines hinter dünnem Adapter, damit dieselbe Strategie durch vectorbt **und** backtesting.py läuft.
- Kleine, fokussierte Module; wächst eine Datei zu groß, ist das ein Signal, dass sie zu viel tut.

## Daten-Caveats (immer mitdenken)
Survivorship Bias · Adjustment-Restatement/Lookahead (`auto_adjust`) · Volumen-Repräsentativität (IEX) · Insider-Verzug. Details: Spec §11. Nie so tun, als wären die freien Daten sauber.
