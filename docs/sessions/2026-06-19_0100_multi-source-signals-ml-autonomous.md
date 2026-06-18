# Session-Handoff — 2026-06-19

> Für den nächsten Chat: hier ist der vollständige Stand. Repo `signal-trader-demo`. Branch **`feat/phase-3-dashboard-forward`** (Phase 2 ist bereits in `main`). Tests: **196 grün**, ruff clean. Reply Deutsch, Code/Commits Englisch. Locked decisions in `CLAUDE.md`/`PROJECT.md` gelten unverändert.

## Was das Produkt jetzt ist
Lokales, ehrliches **Mess-Harness** mit **4 Signalquellen** → Dashboard (FastAPI + React 19, KIT-Design), alles point-in-time, Datenverzug ehrlich ausgewiesen, **kein Echtgeld** (außer Nico handelt Vorschläge manuell am Handy).

**Die 4 Quellen (alle gratis, point-in-time):**
1. **Insider Form 4** — marktweiter Scan (`scripts/scan_insider_market.py`): zieht alle Form 4, funnelt auf Issuer mit 3–25 Filings (kleine fokussierte Cluster, Mega-Cap-Churn raus), ≥3-Insider-Kauf-Cluster. Findet auch junge/kleine Werte (STRR ~11$, MBC ~9$).
2. **13F Superinvestoren** (`sources/superinvestor_13f.py`, `scripts/ingest_13f.py`) — Burry/Buffett/Ackman/Tepper/Dalio, NUR neue Long-Aktienkäufe (Puts ignoriert!), Konsens ≥2 Fonds. Live: GOOG, SNDK.
3. **US-Abgeordnete (House STOCK Act)** (`sources/congress_trades.py`, `scripts/ingest_congress.py`) — House Clerk Bulk-XML (Offenlegungsdatum = PIT) + PTR-PDF-Parse (pypdf). Konsens ≥2 Politiker. Live: HD (6 Abgeordnete), GS (5), PEP/PG/V/BA (4). Ehrlich: meist Blue-Chips, kein Hype.
4. **ML-Paper (autonom)** — LightGBM, siehe unten.

## ML-Modell (Phase 4, `strategy/shortterm/`)
- LightGBM-Regressor, 5-Tage-Forward-Return, Long-Top-k. Features: Multi-Window-Renditen + Vola (NUR Kurs). Purged+embargoed Walk-Forward, nach Kosten vs. Momentum-Baseline, PSR.
- **Ergebnisse (OOS):** klein (84 Pkt) → verliert; retro breit (75–108 Namen, 630 Pkt) → **schlägt Baseline knapp** (+0,50% vs +0,36%/Rebalance).
- **Survivorship-Check:** Edge hält auf breiterem Universum (~0,14% Marge), aber **kein sauberer Test** (yfinance hat keine delisteten Namen → bräuchte bezahlten Feed). Beide PSR hoch (14-J-Bullenmarkt).
- **Overfitting-Beweis:** Kalender-Features hinzugefügt → OOS **schlechter** → wieder entfernt (`_add_calendar` existiert, default aus). **Lektion: mehr Parameter = Overfitting; OOS ist der Richter.**
- Autonomer Paper-Loop: `scripts/paper_trade_ml.py` (trainiert auf `data/ml_cache.sqlite`, eröffnet Top-k Alpaca-**Paper**-Orders). Bewusst NICHT real-verifiziert → nur Üben.

## Autonome Jobs (Windows Task Scheduler, brauchen PC an)
- `SignalHarness-DailyRefresh` (täglich 22:00): Namen-Cache + Insider-Scan + 13F + Congress → Vorschläge frisch. (`scripts/daily_refresh.sh`)
- `SignalHarness-MLPaper` (Mo–Fr 15:40 = nach US-Open): autonomer ML-Paper-Trade.
- Desktop: `Signal Harness.lnk` (KIT-Icon) startet `scripts/desktop_app.sh` → uvicorn serviert API+gebautes Frontend auf :8000.

## UI-Stand (zuletzt verbessert)
- **Firmennamen groß** (SEC-Ticker→Name-Liste, `market_data/company_names.py`, gecacht `data/ticker_names.json`), Kürzel klein.
- Vorschläge **absteigend nach Score** sortiert.
- **Klartext-Summary** pro Karte ("N Insider/Abgeordnete/Star-Investoren kauften {Firma}: Namen. Öffentlich seit {Datum} (Verzug).") — deterministisch, KEINE LLM-Spekulation.
- Quellen-Links in einklappbares "▸ Quellen ansehen".
- **Nico ist mit dem Design noch nicht zufrieden** → Dummy-Mockup liegt in seinem Windows `Downloads/signal-harness-mockup.html` (für Claude Design).

## Offene Punkte / Blocker (brauchen Nico oder Entscheidung)
- **FMP-API-Key** (`FMP_API_KEY` in `.env`) — für Senat-Trades + Fundamental-Features (Income-Statement ist PIT via `acceptedDate`, guter ML-Feature-Kandidat). Noch nicht gesetzt. Endpoint `senate-trades` muss getestet werden, ob Free-Tier ihn freischaltet.
- **X/Twitter** — kein gratis Weg (Login-Wall/Bot-Block/ToS, kein ehrlicher Backtest). Braucht bezahlte X-API (~200$/Mo). **Empfehlung: weglassen** (schwächstes Signal).
- **Ollama** — installiert, aber Server/Modell nicht aktiv. Optional für schönere Summary-Formulierung (NUR Fakten umformulieren, nie Gründe erfinden).
- **Transaktionsdatum** in Summary noch nicht durchgereicht (aktuell nur Offenlegungsdatum) — Nico wollte evtl. "wann gekauft".
- **TSM-Insider-Anzahl (31)**: echte Personen, aber unrealistisch viel → Skepsis-Flag, per SEC-Link prüfbar. Filter ggf. härten (Personen vs. Entitäten).
- **Sauberer Survivorship-Test** des ML braucht delisteten-Preis-Feed (CRSP/Sharadar/Norgate — paid).

## Nächste sinnvolle Schritte (autonomer Backlog)
1. Insider-/Politiker-Konsens als **ML-Feature** (orthogonale Info, ehrlich OOS testen — Council-Top-Idee).
2. FMP-Fundamental-Features (sobald Key da).
3. Transaktionsdatum in Summary.
4. Design-Überarbeitung nach Nicos Claude-Design-Runde am Mockup.

## Wichtige Dateien
- Quellen: `src/signal_trader/sources/{edgar_form4,superinvestor_13f,congress_trades}.py`
- Pipelines: `src/signal_trader/signals/{insider,superinvestor,congress}/`, `signals/consolidate/suggestion_builder.py`
- ML: `src/signal_trader/strategy/shortterm/{dataset,model,evaluate}.py`, `backtest/validation.py` (`purged_walk_forward`)
- API/Frontend: `src/signal_trader/api/app.py`, `frontend/`
- Scripts: `scripts/{scan_insider_market,ingest_13f,ingest_congress,paper_trade_ml,train_ml_retro,run_api,daily_refresh.sh}.py`
- Pläne: `docs/superpowers/plans/2026-06-18-phase-{3,4}-*.md` (mit Outcome-Abschnitten)

## Iron principles (nicht verletzen)
Ehrliches Harness vor Performance; kein Edge-Versprechen; point-in-time Pflicht; nach Kosten + Baseline + PSR; kein LLM-Kursprognose; paper-only in der App; kein silent truncation; Tests offline (keine Live-Calls). "Mehr Parameter" nur wenn OOS es belegt.
