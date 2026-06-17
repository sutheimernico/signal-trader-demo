# signal-trader-demo

Lokale, kostenfreie **Paper-Trading-Demo** und Backtest-Harness mit echten Aktiendaten. Zwei Spuren: ein langfristiges, signalbasiertes Vorschlagsystem (Insider-Cluster-Käufe; Nutzer entscheidet final) und ein abgegrenztes kurzfristiges ML-Experiment.

> **Kein Anlageprodukt, keine Anlageberatung.** Ausschließlich Paper-Trading, zu Lern- und Engineering-Zwecken. Das Ziel ist ein *ehrliches Mess-Harness*, kein Edge-Versprechen — für Retail ist kurzfristiges Alpha realistisch nicht erreichbar.

## Status
**Phase 1 (Fundament) abgeschlossen** — Daten-Cache, zwei Backtest-Engines (vectorbt + backtesting.py) mit Kosten/Slippage, Momentum-Baseline, Shift-Test/OOS/Walk-forward, Metriken (CAGR/Sharpe/Sortino/Calmar/MaxDD/PSR) gegen Benchmark nach Kosten, Break-even-Check, Alpaca-Paper-Stub. 71 Tests grün. Nächster Schritt: Phase 2 (Insider-Signale). Details & Outcome: `docs/superpowers/plans/2026-06-17-phase-1-foundation.md`.

Foundation-Report selbst ausführen: `uv run python scripts/backfill.py --tickers AAPL --start 2020-01-01 --end 2024-01-01` dann `uv run python scripts/run_backtest.py --ticker AAPL`.

## Dokumente
- `PROJECT.md` — Source of Truth (Spec, Roadmap, Entscheidungen, Open Inputs)
- `docs/superpowers/specs/2026-06-17-signal-trader-demo-design.md` — Design-Tiefe, Recherche, Belege
- `CLAUDE.md` — Arbeitsweise & Locked Decisions · `AGENTS.md` — Codebase-Operatives

## Daten-Caveats (wichtig)
Freie Datenquellen sind nicht sauber. Bewusst behandelt: **Survivorship Bias**, **Adjustment-Restatement/Lookahead**, **Volumen-Repräsentativität** (IEX), **Insider-Verzug**. Siehe Spec §11.

## Setup
Wird in Phase 0 etabliert (Python via `uv`). Externe Zugänge (alle kostenlos): Alpaca Paper-Account, SEC-User-Agent-Kontakt, optional Tiingo. Keys nur via `.env` (nie committen).
