# signal-trader-demo

Lokale, kostenfreie **Paper-Trading-Demo** und Backtest-Harness mit echten Aktiendaten. Zwei Spuren: ein langfristiges, signalbasiertes Vorschlagsystem (Insider-Cluster-Käufe; Nutzer entscheidet final) und ein abgegrenztes kurzfristiges ML-Experiment.

> **Kein Anlageprodukt, keine Anlageberatung.** Ausschließlich Paper-Trading, zu Lern- und Engineering-Zwecken. Das Ziel ist ein *ehrliches Mess-Harness*, kein Edge-Versprechen — für Retail ist kurzfristiges Alpha realistisch nicht erreichbar.

## Status
**Phasen 1–4 abgeschlossen**, methodisch reviewt, vollständig offline testbar (238 Tests grün, ruff clean; Live-Calls nie im Test):
- **Phase 1 — Fundament:** Daten-Cache, zwei Backtest-Engines (vectorbt + backtesting.py) mit Kosten/Slippage, Momentum-Baseline, Shift-Test/OOS/Walk-forward, Metriken (CAGR/Sharpe/Sortino/Calmar/MaxDD/PSR) gegen Benchmark nach Kosten, Break-even-Check, Alpaca-Paper-Stub.
- **Phase 2 — Spur 1 (Insider):** SEC Form 4, Filter (opportunistic/Cluster/Small-Cap), point-in-time Signal-Logging, Trefferquoten; 13F + Congress als zusätzliche freie PIT-Quellen.
- **Phase 3 — Dashboard + Forward-Paper:** FastAPI Read-API, React-19-Dashboard, voller Alpaca-Paper-Loop (Live-Smoke braucht Keys → Needs Nico).
- **Phase 4 — Spur 2 (ML):** GBDT, purged + embargoed Walk-forward, OOS nach Kosten vs. Baseline + PSR/diff-PSR/Shift-Test, opt-in Consensus-Feature, **FREE synthetic-delisting Survivorship-Stresstest**.

Foundation-Report selbst ausführen: `uv run python scripts/backfill.py --tickers AAPL --start 2020-01-01 --end 2024-01-01` dann `uv run python scripts/run_backtest.py --ticker AAPL`.

## Honest harness — gemessene Artefakte (keine Edge-Behauptung)
Jede Zahl ist gemessen, nie geschätzt. Die belastbaren Größen sind der **Margin vs. Baseline** (`diff-PSR`, `beats baseline?`) und der **Shift-Test**, nicht die regime-aufgeblähten absoluten PSRs (Bull-Markt, überlappende Horizonte).

**ML vs. Momentum-Baseline (OOS, nach Kosten):** Ein naiver Preis-Feature-GBDT **schlägt die Momentum-Baseline nicht** robust (`diff-PSR` < 0.5 in allen Armen). Das ist der erwartete, ehrliche Befund — für Retail ist kurzfristiges Alpha realistisch nicht erreichbar. Reported als Lern-Artefakt, nicht versteckt. Details: `docs/superpowers/plans/2026-06-18-phase-4-ml-experiment.md`.

**Survivorship-Stresstest (das Headline-Artefakt, FREE):** Die OOS-Evaluation läuft survivors-only — yfinance liefert für wirklich delistete Namen keine Kurse. Der Stresstest bestraft point-in-time jeden Universums-Namen, der später delistete/havarierte, mit einem Haircut (−40/−60/−100 %) und lässt denselben purged+embargoed Walk-forward erneut laufen. Gemessen auf dem lokalen 108-Namen-Cache (2013–2026, 252 OOS-Rebalances, 14 reale Decliner geshadet):

| Lauf | ML net/Rebal | Baseline net/Rebal | diff-PSR | beats baseline? |
|---|---|---|---|---|
| survivors-only | +0.0088 | +0.0135 | 0.10 | nein |
| Stress −0.40 | −0.0179 | −0.1186 | 1.00 | **ja** |
| Stress −0.60 | −0.0204 | −0.1816 | 1.00 | **ja** |
| Stress −1.00 | −0.0126 | −0.3075 | 1.00 | **ja** |

**Ehrliche Lesart — wichtig:** „ML schlägt die Baseline unter Stress" heißt **nicht** „ML hat einen Edge". Beide verlieren unter Stress Geld (ML absolut weiterhin negativ). Der Grund ist Baseline-Fragilität: die Momentum-Baseline pickt einen geshadeten (fragilen) Decliner in **31,5 %** der Picks (sie jagt deren Momentum-Spikes), der GBDT nur in **3,3 %**. Der GBDT ist also strukturell weniger survivorship-anfällig als naives Momentum — ein gemessener, belastbarer Befund, keine Alpha-Behauptung.

**Ehrliche Grenzen (dokumentiert, nicht versteckt):** Der Test ist eine **partielle, konservative** Korrektur — nur Namen, die zugleich im (Survivor-)Universum **und** auf der freien Delisting-Liste stehen, können geshadet werden; die Masse der delisteten Namen fehlt im Universum und ist ohne bezahlte Kurse (CRSP/Sharadar — **Needs Nico**) nicht rückholbar. Die freie Liste (SEC Form 25/25-NSE) mischt M&A/freiwillige Delistings mit Bankrott — ein geshadeter Name „verließ das Listing", ging nicht zwingend „bankrott". Der Haircut ist eine transparente Annahme; deshalb ein Sensitivitätsband statt einer Magic Number.

Selbst ausführen (braucht den ML-Cache + optional `data/delistings.csv` via `scripts/ingest_delistings.py`, SEC-Identity nötig):
```bash
uv run python scripts/run_ml_experiment.py --tickers AAPL MSFT INTC ... \
    --start 2013-01-01 --end 2026-06-17 --no-trade \
    --survivorship-stress --delisting-haircut -0.60
```

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
