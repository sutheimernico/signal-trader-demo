# Signal-Trader-Demo — Design

**Stand:** 2026-06-17 · **Status:** Design, zur Review
**Source of Truth:** `PROJECT.md` · **Grundlage:** Original-Konzept des Nutzers (KI-Trading-Demo) + drei Recherche-Durchläufe (Backtest-Methodik, Signalquellen, ML/LLM-Realität).

Dieses Dokument hält das *Warum* fest: Entscheidungen, verworfene Alternativen, die ehrliche Einordnung und die Belege. `PROJECT.md` ist die schlanke, bindende Ableitung daraus.

---

## 1. Was das ist — und was nicht

Eine **lokale, kostenfreie, ausschließlich auf Paper-Trading laufende Backtest- und Paper-Trading-Plattform**. Sie unterstützt zwei Spuren:

- **Spur 1 (langfristig):** Ein Vorschlagsystem aus öffentlichen Signalen (Kern: Insider-Cluster-Käufe). Der Nutzer entscheidet final.
- **Spur 2 (kurzfristig):** Ein sauber abgegrenztes ML-Experimentierfeld.

**Das eigentliche Deliverable ist nicht „schlägt den Markt", sondern ein ehrliches Mess-Harness** — und die Fähigkeit, einen *scheinbar guten* Backtest als Artefakt zu entlarven. Diese Rahmung ist nicht Bescheidenheit, sie folgt aus der Faktenlage (§3). Sie ist auch die Verteidigung gegen den häufigsten Fehlermodus solcher Projekte: ein Modell auf einem ungetesteten Datenpfad zu bauen, dessen Backtest-Erfolg man nicht von Selbstbetrug unterscheiden kann.

## 2. Ziele und Nicht-Ziele

**Ziele**
- Reproduzierbares Backtest-Harness mit Kosten/Slippage, Walk-forward/OOS und ehrlichen Metriken gegen einen Benchmark nach Kosten.
- Spur 1 bis zu einem nutzbaren Vorschlag-Dashboard mit Trefferquoten-Tracking.
- Spur 2 als methodisch sauberes, abgegrenztes Experiment.
- Forward-Betrieb im Paper-Modus als Pipeline-Validierung.

**Nicht-Ziele (jetzt)**
- Echtgeld-Handel; vollautonome Ausführung in Spur 1.
- Kostenpflichtige Echtzeit-Feeds; Sekunden-genaues News-Scalping; Nicht-US-Märkte in v1.
- Signale aus Trades deutscher/EU-Politiker (es gibt keine Trade-Level-Daten — bestätigt, §12).
- LLM-basierte Kursprognose (methodische Falle, §13).

## 3. Ehrliches Framing — warum kein Geld-Versprechen

Die Recherche ist hier eindeutig:

- **Retail + kurzfristig ≈ unmöglich.** Kurzfrist-Returns sind nahe am Random Walk; der prognostizierbare Varianzanteil ist winzig. Das kanonische ML-Asset-Pricing-Paper (Gu/Kelly/Xiu) erreicht mit besten Modellen **~0,3–0,4 % monatliches Out-of-Sample-R²** — auf Monatsbasis, mit Institutionsdaten und 900+ Prädiktoren. Kürzere Horizonte sind verrauschter, nicht weniger.
- **ML-Profite konzentrieren sich, wo Retail am schwächsten ist** (Micro-Caps, illiquide, hochvolatil) und verschwinden nach realistischen Kosten weitgehend (Avramov/Cheng/Metzker, Management Science 2023).
- **Insider-Alpha ist überhyped für Außenstehende.** Die berühmten 9–22 %/Jahr werden ab *Trade-Datum* gemessen (private Information). Aktuelle Arbeit findet, dass **70–80 % des Alphas vor der Veröffentlichung** anfallen; was nach dem Filing bleibt (~20–30 %) lebt in Micro-Caps, wo Spreads/Impact den Rest fressen.
- **2–4 Wochen Forward-Paper beweisen nichts über Performance.** Eine Low-Frequency-Strategie macht in dem Zeitraum eine Handvoll Trades → statistisch null Aussagekraft. Der Forward-Run ist **Plumbing-Validierung**, keine Performance-Aussage. Die ehrliche Bewertung kommt aus dem Backtest.

Konsequenz: Wir framen jeden Output als Lern- und Engineering-Artefakt, nie als Edge-Behauptung. Ein Modell darf erst „interessant" heißen, wenn es Baseline **und** naive Referenz unter sauberer Validierung nach Kosten schlägt.

## 4. Architektur

Fünf Schichten, klar getrennt (aus dem Original-Plan übernommen). In v1 zünden nur die unteren — die oberen sind verdrahtet, aber leer.

```
[ Data Layer ]      Marktdaten + (später) Signalquellen einlesen, normalisieren, cachen      v1
[ Signal Layer ]    Pro Quelle Signale, pro Aktie konsolidieren, Scoring + Hit-Rate          Phase 2
[ Strategy Layer ]  Spur 1: Vorschlagslogik  ·  Spur 2: ML-Pipeline                          Phase 2 / 4
[ Sim Layer ]       Backtest-Engine(s) + Alpaca Paper Trading                                 v1 (Backtest) / Phase 3 (voll)
[ Interface Layer ] Dashboard: Vorschläge, Signalkarten, Trefferquoten, Performance          Phase 3
```

## 5. v1 (Fundament) — Scope & Definition of Done

Gewählt: **„Backtest komplett, Live nur Stub"** auf **S&P-500-Tagesdaten**. Done, wenn:

1. **Datenanbindung:** Tages-Bars des S&P-500-Universums werden einmal gezogen und lokal gecacht (Parquet/SQLite); Backtests laufen gegen den Cache (reproduzierbar, umgeht Rate-Limits). Datenquelle hinter dünner Provider-Schnittstelle (yfinance jetzt, Tiingo-Upgrade später).
2. **Backtest-Engine(s):** `vectorbt` (Sweeps) **und** `backtesting.py` (event-driven) — dieselbe Baseline durch beide, mit **Flat-per-Trade-Kosten + Slippage** und **Break-even-Cost-Check** (ab welchen Kosten fällt der Sharpe auf 0?).
3. **Baseline:** Eine transparente Momentum-Regel, nur zur Harness-Validierung.
4. **Leakage-/Validierungs-Disziplin:** **Shift-Test** (alle Inputs um 1 laggen → bricht die Performance ein, war Leakage drin), **Out-of-Sample-Hold-out** (nie zur Modellwahl angefasst), **anchored Walk-Forward**.
5. **Metriken:** CAGR, Sharpe, **Sortino + Calmar** (nie Sharpe allein — die Divergenz ist die Information), Max Drawdown; immer gegen **Buy-and-Hold-Benchmark, beide nach Kosten**; plus eine ~30-Zeilen-**PSR** (Probabilistic Sharpe Ratio).
6. **Persistenz + Datenmodell** (§9) angelegt.
7. **Alpaca-Paper als dünner, getesteter Stub:** eine Test-Order durchstellen. Volles Order-Routing/PnL erst Phase 3.

**Bewusstes Fundament-Deliverable:** Die Demonstration „dieselbe Strategie sieht vektorisiert besser aus als event-driven mit realistischen Fills" ist als Lernartefakt stärker als ein einzelner sauberer Backtest.

## 6. Stack-Entscheidungen (recherche-gestützt)

| Bereich | Entscheidung | Begründung / verworfene Alternative |
|---|---|---|
| Sprache | Python | Data/Signals/Backtest/ML. |
| DB | **SQLite** + Parquet-Cache | Lokal, Single-User → PostgreSQL (Original-Plan) ist verfrüht. |
| Marktdaten | **yfinance-first** hinter Provider-Seam, gecacht | Schnellster Start, kein Signup. Caveats dokumentiert (§11). *Verworfen:* Tiingo-first (sauberer, aber Account + Stunden-langer Rate-limitierter Erst-Backfill bei 500 Tickern); Alpaca-Feed (Free = nur IEX, ~3–4 % Volumen). Tiingo bleibt dokumentiertes Upgrade. |
| Backtest | **vectorbt** (Sweeps) + **backtesting.py** (event-driven) | Zwei-Stufen-Muster mit Lernwert. *Verworfen:* `backtrader` (faktisch Archive-Mode seit ~2020); vectorbtpro (bezahlt); nautilus_trader (Realismus-Goldstandard, aber Overkill für Demo). |
| Metriken | **quantstats-reloaded** + eigene PSR | Quantopian-Originale (`quantstats`/`pyfolio`/`empyrical`) sind unmaintained. PSR/DSR bietet keine Mainstream-Lib first-class. |
| Paper-Trading | **alpaca-py** (`paper=True`) | Offizielles SDK (`alpaca-trade-api` deprecated). Tagesbars ausreichend. Gotcha: Paper-Fills optimistisch (keine Slippage/Dividenden) → eigene Kostenmodellierung im Backtest. |
| ML (Phase 4) | **LightGBM/GBDT** Default; Qlib optional | DL (LSTM/Transformer) schlägt Trees auf tabellarischen Finanzdaten nicht konsistent (Grinsztajn et al.; DLinear). Microsoft Qlib bringt point-in-time-Datenlayer. *Verworfen als Edge:* FinRL/RL (Hype, Overfitting-/Non-Stationaritäts-Killer), mlfinlab (inzwischen proprietär). |
| LLMs | **In v1 raus** | Knowledge-Cutoff-Confound macht News-Backtests zu Selbstbetrug (§13). |
| Web | FastAPI (backend) + React 19 (frontend) | Erst Phase 3. React bewusst als Lern-Wachstumsfeld des Nutzers. |

## 7. Roadmap

- **Phase 0 — Scaffold:** Repo, Struktur, Doku, Agents, Skills, `pyproject`/Deps gepinnt, Open Inputs (Accounts/Keys).
- **Phase 1 — Fundament:** §5 DoD. ← *Einstieg.*
- **Phase 2 — Spur 1 (Insider):** SEC Form 4 via `edgartools`, Filter (opportunistic + Code „P" + Cluster + Small-Cap-Tilt), Konsolidierung pro Aktie, Signal-Logging mit `event`/`known`-Zeit + Kurs, Trefferquoten. 13F als zweites, sauberes Übungs-Dataset (kein Edge-Framing).
- **Phase 3 — Dashboard + Forward-Paper:** Signalkarten, Nutzerentscheidung, Trefferquoten, Datenverzug sichtbar; voller Alpaca-Paper-Loop (Order-Routing, Position/PnL, Scheduler).
- **Phase 4 — Spur 2 (ML):** Cross-sectional Ranking oder Vol-/Regime-Forecast (nicht Einzelaktien-Punktprognose). Muss Baseline + naive Referenz unter purged/embargoed-Validierung nach Kosten schlagen.

## 8. Eiserne Prinzipien → Akzeptanzkriterien

1. Backtest rechnet Transaktionskosten und Slippage standardmäßig ein.
2. Jedes Signal wird mit Ereigniszeit (`timestamp_event`), Bekanntwerden-Zeit (`timestamp_known`) und Kurs protokolliert.
3. Trefferquote je Quelle aus tatsächlichen Folge-Ergebnissen, im Dashboard sichtbar.
4. Datenverzug jeder Quelle im System sichtbar.
5. Jede Strategie-Evaluierung nutzt Walk-forward bzw. OOS-Trennung; Leakage wird per Shift-Test geprüft.
6. Performance immer gegen breiten Benchmark, **nach Kosten**; nie Sharpe allein (Sortino + Calmar + PSR dazu).
7. Vollständig kostenfreie Datenquellen, kein bezahlter Feed.
8. In Spur 1 entscheidet der Nutzer final; das System schlägt nur vor.
9. Daten-Caveats (§11) sind im System/README dokumentiert.
10. Der Forward-Run wird als Plumbing-Validierung ausgewiesen, nicht als Performance-Beleg.

## 9. Datenmodell (Skizze, aus dem Original-Plan)

- **Signal:** `ticker, source, signal_type, direction, timestamp_event, timestamp_known, price_at_known, raw_payload, confidence`
- **Suggestion:** `ticker, consolidated_score, contributing_signals, created_at, status(open/accepted/rejected), horizon(short/long), user_decision, decided_at`
- **SourceScore:** `source, window, n_signals, hit_rate, avg_forward_return, updated_at`
- **PaperTrade:** `ticker, side, qty, entry_price, entry_time, exit_price, exit_time, pnl, source_suggestion_id`
- **PriceBar (neu, Cache):** `ticker, date, open, high, low, close, adj_close, volume, source, fetched_at`

## 10. Repo-Struktur (+ Mapping zum Original-Plan)

Domänen-Layout des Plans, aber als sauberes Python-Package unter `src/` (vermeidet die Code-vs-Daten-Mehrdeutigkeit von `data/`):

```
src/signal_trader/
  market_data/   # Plan: data/market   — Bars ziehen/normalisieren/cachen
  sources/       # Plan: data/sources  — Signalquellen (EDGAR ...)
  store/         # Plan: data/store    — Persistenz, Schema, Repos
  signals/{insider,consolidate,scoring}/
  strategy/{longterm,shortterm}/
  backtest/{engine,baselines}/
  paper/alpaca/
app/{backend,frontend}/
data/            # tatsächlicher Cache (Parquet/SQLite) — gitignored
scripts/  config/  tests/
docs/superpowers/{specs,plans}/  docs/sessions/
.claude/agents/
```

Begründung der Abweichung: proper Package-Import-Pfade, klare Trennung Code/Cache. Reversibel.

## 11. Daten-Caveats (verpflichtend ins README)

1. **Survivorship Bias** — freie Quellen enthalten nur heute lebende Ticker; keine freie Quelle löst das.
2. **Adjustment-Restatement/Lookahead** — `auto_adjust` macht Adjusted Close zu rückwirkend restated Werten → subtiler Lookahead; bewusst handhaben.
3. **Volumen-Repräsentativität** — IEX (Alpaca free) ≈ 3–4 % des Volumens.
4. **Insider-Verzug** — Trade + bis zu 2 Geschäftstage Filing + Polling → realistisch 2–3 Tage hinterher; Alpha vor Veröffentlichung verloren.

## 12. Phase-2-Vorschau — Insider-Signale (Spur 1)

- **Edge real, aber gekürzt:** Cohen/Malloy/Pomorski (routine vs. opportunistic — wer 3 Jahre im selben Kalendermonat handelt = routine, Alpha ≈ 0); Käufe informativ, Verkäufe Rauschen. Außenstehende sehen nur den Rest nach dem Filing.
- **Filter Signal/Rausch:** Code „P" (Open-Market-Kauf); M/A/Vesting/Optionsausübung raus; 10b5-1-Pläne raus; opportunistic-only; Cluster (3+ Insider) bevorzugen; Small/Micro-Cap-Tilt.
- **Daten:** `edgartools` (kein Key, `set_identity(...)` erfüllt SEC-User-Agent-Pflicht; max. 10 req/s). OpenInsider als optionaler Cross-Check; Daily-Index als Notausgang.
- **13F:** SEC Form 13F Data Sets (vorgeparst), strikt ab Filing-Datum rebalancieren. Sauberes Übungs-Dataset, marktnah — kein Edge-Framing.
- **Congress:** nur als Selektionsbias-Lehrstück (Edge weitgehend widerlegt: Belmont et al. 2022). **DE/EU-Politiker: streichen.** BaFin Directors' Dealings nur optional (nur Web-Portal, hoher Scraping-Aufwand).

## 13. Phase-4-Vorschau — ML-Experiment (Spur 2)

- **Rahmung:** Cross-sectional Ranking (relative Ordnung vieler Aktien) ist der seriös dokumentierte ML-Vorteil — nicht Einzelaktien-Punktprognose. Alternativ Vol-Prognose (aber HAR-RV ist schwer zu schlagen) oder Regime-Erkennung (Konditionierungs-Tool).
- **Methodik gestuft:** Must-have: strikter Train/Test-Split (kein Preprocessing auf Testset gefittet), Purging+Embargo bei überlappenden Labels, Triple-Barrier-Labeling, PIT/Survivorship-Bewusstsein. Nice-to-have: Sample-Uniqueness-Weighting, Fractional Differentiation (als Experiment). Skip: Meta-Labeling, CPCV-Formalismus, Deflated-Sharpe-Gate (erst bei breiter Strategiesuche).
- **Modell:** LightGBM mit Rolling-Window-Retraining. DL nur, wenn es getunten Tree **und** naive Baseline unter deflationierten Metriken schlägt.
- **LLM-Falle explizit:** Backtest eines heutigen LLM auf alten News misst Erinnerung, nicht Skill (Knowledge-Cutoff). Ehrlich nur: striktes Point-in-time **plus** Cutoff-Kontrolle, Modell mit Cutoff vor Testzeitraum, oder Forward-Test auf Post-Cutoff-Daten; LLMs allenfalls für Extraktion/Klassifikation mit Zukunftswissen-Audit.

## 14. Council / Agents & Skills

- **Projekt-Agent (Kern):** `backtest-methodology-reviewer` (read-only) — jagt Lookahead, Survivorship, fehlende Kosten, Overfitting, PIT-Verletzungen, Benchmark-Disziplin. Liegt in `.claude/agents/`.
- **Council:** für hochriskante Methodik-Entscheidungen (model-diverse Zweitmeinung) der `council`-Skill.
- **Generische Agents** (global vorhanden): `security-reviewer`, `api-design-reviewer` (FastAPI, Phase 3), `frontend-reviewer` (React, Phase 3), `Explore`, `Plan`.
- **Skills:** Discovery via `find-skills` → Vorschlag → Installation erst nach Go (nichts ungefragt).

## 15. Open Inputs (vom Nutzer, extern)

- Alpaca Paper-Account + API-Keys (Paper-Trading + ggf. Daten). In `.env` (nie committen).
- SEC-User-Agent-Kontakt (`edgartools` `set_identity`) — z. B. Name + E-Mail.
- Optional später: Tiingo Free API-Key (Daten-Upgrade).
- Bestätigung des Doku-Modus: committed (portfolio-Stil) — Standard, falls kein Widerspruch.

## 16. Recherche-Zusammenfassung & Quellen

**Backtest-Methodik/Tooling:** Walk-forward + Shift-Test + OOS reichen für Low-Frequency; Purging/Embargo nur bei überlappenden ML-Labels; CPCV Overkill. Flat-Kosten + Break-even-Check. yfinance fragil aber nutzbar; Alpaca = Paper, nicht Feed.
**Signale:** Insider Form 4 = bester ehrlicher Resteffekt + sauberste freie Anbindung; 13F sauber aber marktnah; Congress = Hype; DE/EU = keine Daten.
**ML/LLM:** v1 ohne ML; GBDT statt DL; LLMs nur forward/post-cutoff; RL = Hype.

Quellen (Auswahl):
- Gu, Kelly & Xiu, *Empirical Asset Pricing via ML* (RFS 2020) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3159577
- Avramov, Cheng & Metzker, *ML vs. Economic Restrictions* (Mgmt Science 2023) — https://ideas.repec.org/a/inm/ormnsc/v69y2023i5p2587-2619.html
- Cohen, Malloy & Pomorski, *Decoding Inside Information* (JF 2012) — https://www.nber.org/papers/w16454
- Jeng, Metrick & Zeckhauser, *Returns to Insider Trading* (2003) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=146029
- Ozlen & Batumoglu, *The Death of Insider Trading Alpha* (SSRN 2024/26) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5966834
- Belmont et al., *Do senators and house members beat the market?* (J. Public Econ 2022) — https://www.sciencedirect.com/science/article/abs/pii/S0047272722000044
- Bailey & López de Prado, *The Deflated Sharpe Ratio* — https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Bailey, Borwein, López de Prado, Zhu, *Probability of Backtest Overfitting* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Grinsztajn et al., *Why tree-based models outperform DL on tabular data* (NeurIPS 2022) — https://arxiv.org/abs/2207.08815
- Zeng et al., *Are Transformers Effective for Time Series Forecasting?* (DLinear, AAAI-23) — https://arxiv.org/pdf/2205.13504
- Lopez-Lira, Tang & Zhu, *The Memorization Problem* (2025) — https://arxiv.org/abs/2504.14765
- Sarkar & Vafa, *Lookahead Bias in Pretrained LMs* (2024) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4754678
- SEC EDGAR APIs + Fair Access — https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- edgartools — https://github.com/dgunning/edgartools
- alpaca-py — https://github.com/alpacahq/alpaca-py
- vectorbt — https://github.com/polakowo/vectorbt · quantstats-reloaded — https://pypi.org/project/quantstats-reloaded/
- Microsoft Qlib — https://github.com/microsoft/qlib

**Vertrauens-Caveats:** Einige SSRN/Journal-Volltexte blockten den Fetch; die CMP-Klassifikationsregel und die 70–80-%-Zahl sind über NBER/Sekundärquellen korroboriert, nicht aus dem Primär-PDF. Cluster-4–8-%- und 13F-Zahlen sind teils Praktiker-/Top-Quartil-Werte, kein robuster Live-Edge.
