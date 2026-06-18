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

**Insider-Verzug (Track 1):** Handelstag + bis zu ~2 Geschäftstage Meldefrist + Polling ⇒ realistisch 2–3 Tage hinterher; Vorveröffentlichungs-Alpha ist nicht verfügbar. `timestamp_known` ist das Filing-Datum und das einzige Datum, das für Trades benutzt wird; `timestamp_event` (Handelstag) wird nur zur Auditierung gespeichert.

## Setup
Wird in Phase 0 etabliert (Python via `uv`). Externe Zugänge (alle kostenlos): Alpaca Paper-Account, SEC-User-Agent-Kontakt, optional Tiingo. Keys nur via `.env` (nie committen).

## Workflows (CLIs)
Alle paper-only; Live-Kontakt (SEC/Alpaca) braucht Keys in `.env`.

```bash
# Insider-Signale aus SEC Form 4 ingesten (gefiltert, point-in-time persistiert)
uv run python scripts/ingest_insider.py --tickers AAPL MSFT --start 2024-01-01 --end 2024-12-31

# Insider-Strategie-Report: beide Engines nach Kosten + Trefferquote/Datenverzug
uv run python scripts/run_insider_report.py --tickers AAPL --start 2024-01-01 --end 2024-12-31

# Forward-Paper-Loop: Suggestions bauen, akzeptierte öffnen, fällige schließen
#   (Plumbing-Validierung, kein Performance-Beleg; Akzeptanz erfolgt im Dashboard)
uv run python scripts/run_forward_paper.py --hold-days 5

# Dashboard-Backend serven (Read-API; das React-Frontend spricht hiermit)
uv run python scripts/run_api.py --port 8000
```

Das Dashboard (React, Phase 3) wird gegen die Read-API gebaut; Design-Brief: `docs/design/2026-06-18-dashboard-design-brief.md`.
