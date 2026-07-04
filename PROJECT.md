# Signal-Trader-Demo — Project (Source of Truth)

**Stand:** 2026-07-02 · **Status:** Phasen 1–4 abgeschlossen (methodisch reviewt, `pytest` grün, `ruff check .` clean; aktuelle Testanzahl: `uv run pytest --collect-only | tail -1`); Fortsetzung offen (Alpaca-Live-Smoke, echte SEC-Delisting-Liste — beide Needs Nico; sonst Härtung/Erweiterung nach Bedarf).
Persönliche Regeln (`~/.claude/CLAUDE.md`) gelten. Design-Tiefe & Belege: `docs/superpowers/specs/2026-06-17-signal-trader-demo-design.md`. Arbeitsweise: `CLAUDE.md`. Codebase-Operatives: `AGENTS.md`. Aktueller Stand im Detail: `README.md` (Status-Abschnitt), Phase-Pläne unter `docs/superpowers/plans/`, letzte Iterationsnotizen: `AUTOPILOT_LOG.md`.

---

# Part I — Specification

## 1 · Vision & non-negotiables
Lokale, kostenfreie, **paper-only** Backtest- und Paper-Trading-Plattform. Zwei Spuren: (1) langfristiges Vorschlagsystem aus öffentlichen Signalen (Nutzer entscheidet final), (2) abgegrenztes ML-Experiment. **Das Deliverable ist ein ehrliches Mess-Harness, kein Edge-Versprechen** — die Faktenlage (Spec §3) lässt für Retail nichts anderes zu. Forward-Paper ist Plumbing-Validierung, kein Performance-Beleg.

## 2 · Architektur
Fünf Schichten: Data → Signal → Strategy → Sim (Backtest + Alpaca Paper) → Interface (Dashboard). v1 zündet Data + Sim (Backtest) + Interface-Stub. Repo-Struktur und Mapping: Spec §10 / `AGENTS.md`.

## 3 · Scope
**Drin:** Marktdaten-Anbindung (S&P 500, Tagesdaten, gecacht), Backtest-Engine(s) mit Kosten/Slippage, Baseline, Walk-forward/OOS + Shift-Test, Metriken gegen Benchmark nach Kosten, Persistenz, Alpaca-Paper-Stub. Später: Insider-Signale, Dashboard, voller Paper-Loop, ML-Experiment.
**Draußen:** Echtgeld, vollautonome Ausführung in Spur 1, bezahlte Feeds, News-Scalping, Nicht-US-Märkte (v1), DE/EU-Politiker-Trades (keine Daten), LLM-Kursprognose.

## 4 · Datenmodell
`Signal`, `Suggestion`, `SourceScore`, `PaperTrade`, `PriceBar` — Felder siehe Spec §9. Kernprinzip: jedes Signal mit `timestamp_event` **und** `timestamp_known` + Kurs.

## 5 · Tech-Stack
Python · SQLite + Parquet-Cache · yfinance (hinter Provider-Seam, Tiingo-Upgrade später) · vectorbt + backtesting.py · quantstats-reloaded + eigene PSR/DSR (Bailey/López de Prado) + PBO/CSCV-Overfitting-Check · matplotlib (self-built HTML-Tearsheet) · alpaca-py (paper) · FastAPI + React 19 (Phase 3) · LightGBM/Qlib (Phase 4). Begründungen: Spec §6.

## 6 · Acceptance criteria
1. Kosten + Slippage standardmäßig im Backtest.
2. Jedes Signal mit `event`/`known`-Zeit + Kurs protokolliert.
3. Trefferquote je Quelle aus echten Folge-Ergebnissen, im Dashboard sichtbar.
4. Datenverzug je Quelle sichtbar.
5. Walk-forward/OOS für jede Evaluierung; Leakage per Shift-Test geprüft.
6. Performance immer gegen Benchmark **nach Kosten**; nie Sharpe allein (Sortino + Calmar + PSR).
7. Vollständig kostenfreie Datenquellen.
8. In Spur 1 entscheidet der Nutzer final.
9. Daten-Caveats dokumentiert (Spec §11).
10. Forward-Run als Plumbing-Validierung ausgewiesen.

---

# Part II — Plan & working method

## Roadmap
- **Phase 0 — Scaffold:** ✅ Repo/Struktur/Doku/Agents/Skills, `pyproject`/Deps gepinnt, Open Inputs.
- **Phase 1 — Fundament:** ✅ Daten-Cache, vectorbt + backtesting.py mit Kosten/Slippage + Break-even-Check, Momentum-Baseline, Shift-Test + OOS + Walk-forward, Metriken + Benchmark + PSR, Persistenz, Alpaca-Paper-Stub.
- **Phase 2 — Spur 1 (Insider):** ✅ Form 4 via edgartools, Filter (opportunistic + „P" + Cluster + Small-Cap), Konsolidierung, Signal-Logging, Trefferquoten. 13F + Congress als weitere freie PIT-Quellen (über Plan hinaus).
- **Phase 3 — Dashboard + Forward-Paper:** ✅ Signalkarten, Nutzerentscheidung, Trefferquoten, Datenverzug; voller Alpaca-Paper-Loop (Live-Smoke braucht Keys → Needs Nico).
- **Phase 4 — Spur 2 (ML):** ✅ Cross-sectional GBDT, purged/embargoed Walk-forward, OOS nach Kosten vs. Baseline (schlägt Baseline nicht robust — erwarteter, ehrlicher Befund) + FREE Survivorship-Stresstest (Headline-Artefakt).
- **Fortsetzung (offen):** kein neuer Phasen-Scope geplant; nächste Schritte sind Härtung/Erweiterung bestehender Spuren oder die beiden Needs-Nico-Punkte, sobald verfügbar. Details siehe README-Status + `docs/superpowers/plans/`.

## Working method
Superpowers-Flow (`brainstorming → writing-plans → executing/subagent-driven → verification-before-completion`). Zyklus-Gate je Phase: Umsetzung → Messung/Verifikation → kurzer Report → Nico-Freigabe → nächste Phase. Self-Review iterativ pro Arbeitsschritt. Details: `CLAUDE.md`.

## §Decisions (register — closed, dated)
- **2026-06-17** Start mit **Fundament zuerst** (nicht beide Spuren parallel, nicht ML zuerst).
- **2026-06-17** v1-Tiefe: **Backtest komplett, Alpaca-Live nur Stub**.
- **2026-06-17** Universum: **S&P 500, Tagesdaten**.
- **2026-06-17** Datenquelle v1: **yfinance hinter Provider-Seam**; Tiingo dokumentiertes Upgrade.
- **2026-06-17** Backtest: **zwei Engines** (vectorbt + backtesting.py); backtrader verworfen.
- **2026-06-17** DB: **SQLite** statt PostgreSQL.
- **2026-06-17** **Kein ML, keine LLMs in v1**; ML als abgegrenztes Phase-4-Experiment (GBDT-Default).
- **2026-06-17** Repo: Domänen-Layout als `src/`-Package; Doku **committed** (portfolio-Stil).

## §Open inputs (living — external facts Nico owns)
- [x] Alpaca Paper-Account + API-Keys (→ `.env`) — Keys vorhanden (Stand AUTOPILOT_LOG 2026-06-26); der Live-Order-Roundtrip selbst ist bewusst nicht autonom gefeuert (stateful network action) und bleibt unter "Needs Nico" in `AUTOPILOT.md`.
- [x] SEC-User-Agent-Kontakt für edgartools (Name + E-Mail) — `SEC_IDENTITY` gesetzt (Stand AUTOPILOT_LOG 2026-06-26); der Live-Delisting-Fetch bleibt aus demselben Grund unter "Needs Nico".
- [ ] Optional: Tiingo Free API-Key (Daten-Upgrade) — weiterhin offen, kein Blocker (yfinance ist der v1-Default).
- [x] Git: Remote/Visibility — public auf GitHub (`sutheimernico/signal-trader-demo`, Entscheidung 2026-07-04); Commit-E-Mails vor dem Publish auf die noreply-Adresse umgeschrieben.
