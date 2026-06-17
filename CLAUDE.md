# Signal-Trader-Demo — Arbeitsweise & Locked Decisions

Globale persönliche Regeln (`~/.claude/CLAUDE.md`) gelten. Diese Datei ergänzt projekt-spezifisch. Source of Truth: `PROJECT.md`. Design/Belege: `docs/superpowers/specs/`.

## Locked decisions (2026-06-17)
- **Ehrliches Harness vor Performance.** Kein Output wird als Edge geframt; jeder als Lern-/Engineering-Artefakt. Der Forward-Paper-Run ist Plumbing-Validierung, nie Performance-Beleg.
- **Fundament zuerst**, dann Spur 1 (Insider), dann Dashboard/Forward, dann ML. Nie ML auf ungetestetem Datenpfad.
- **Paper-only.** Niemals Echtgeld-Handel verdrahten.
- **Point-in-time ist Pflicht.** Jedes Signal mit `timestamp_event` + `timestamp_known` + Kurs. Backtests gegen den Cache, nie gegen Live-Restated-Daten.
- **Kosten/Slippage immer; Benchmark nach Kosten immer; nie Sharpe allein.**
- **Kein ML/keine LLMs in v1.** LLM-Kursprognose ist durch Knowledge-Cutoff kontaminiert — verboten.

## Wie Claude hier arbeitet
- **Flow:** Superpowers — `brainstorming` (unklarer Scope) → `writing-plans` (Plan vorlegen, auf Go warten) → `executing-plans`/`subagent-driven-development` → `verification-before-completion` vor jeder Fertig-Meldung. Triviales direkt.
- **Phasen-Gate:** Pro Phase: Umsetzung → Messung/Verifikation → kurzer Report → Nico-Freigabe → nächste Phase.
- **Self-Review:** iterativ pro Arbeitsschritt (Korrektheit, Einfachheit, Leakage, Repo-Konventionen), nicht erst vor dem PR.
- **Methodik-Review:** Bei Backtest-/Strategie-/Feature-Code den `backtest-methodology-reviewer` (`.claude/agents/`) laufen lassen — er jagt Lookahead, Survivorship, fehlende Kosten, Overfitting. Bei hochriskanten Methodik-Entscheidungen `council` für model-diverse Zweitmeinung.
- **Orchestrierung:** Read/Recherche/Review/Sweeps an Subagents (nur Konklusion zurück). Write/Build mit Abhängigkeiten single-threaded inline.

## Conventions
- Code, Bezeichner, Kommentare, Commits, Doku auf Englisch; Chat auf Deutsch.
- Conventional Commits, kleine atomare Commits. Nie direkt auf `main` — vor jeder Änderung Branch (`feat/…`, `fix/…`).
- Einfachste Lösung, die das Ziel erfüllt. Kein Overengineering. Neue Deps nur mit Begründung, gepinnt.
- Neue Logik kommt mit Test. LLM-/Netz-gebundener Code hinter Schnittstelle, in Tests gefakt — keine Live-Calls in Tests.

## Security
- Keine Secrets im Code. `.env` nie lesen/ausgeben/committen. Alpaca-/Tiingo-Keys nur via Env.
- SEC fair access: User-Agent mit Kontakt setzen (`edgartools.set_identity`), max. 10 req/s.

## Plan, spec & session docs
- Source of Truth: `PROJECT.md`. Design-Tiefe: `docs/superpowers/specs/YYYY-MM-DD-*.md`. Implementierungspläne: `docs/superpowers/plans/YYYY-MM-DD-*.md`. Session-Handoffs: `docs/sessions/YYYY-MM-DD_HHMM_*.md`.
- Doku ist **committed** (portfolio-Stil).
