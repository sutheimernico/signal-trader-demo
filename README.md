# signal-trader-demo

Lokale, kostenfreie **Paper-Trading-Demo** und Backtest-Harness mit echten Aktiendaten. Zwei Spuren: ein langfristiges, signalbasiertes Vorschlagsystem (Insider-Cluster-Käufe; Nutzer entscheidet final) und ein abgegrenztes kurzfristiges ML-Experiment.

> **Kein Anlageprodukt, keine Anlageberatung.** Ausschließlich Paper-Trading, zu Lern- und Engineering-Zwecken. Das Ziel ist ein *ehrliches Mess-Harness*, kein Edge-Versprechen — für Retail ist kurzfristiges Alpha realistisch nicht erreichbar.

## Status
Phase 0 → Phase 1 (Fundament). Code folgt dem Implementierungsplan unter `docs/superpowers/plans/`.

## Dokumente
- `PROJECT.md` — Source of Truth (Spec, Roadmap, Entscheidungen, Open Inputs)
- `docs/superpowers/specs/2026-06-17-signal-trader-demo-design.md` — Design-Tiefe, Recherche, Belege
- `CLAUDE.md` — Arbeitsweise & Locked Decisions · `AGENTS.md` — Codebase-Operatives

## Daten-Caveats (wichtig)
Freie Datenquellen sind nicht sauber. Bewusst behandelt: **Survivorship Bias**, **Adjustment-Restatement/Lookahead**, **Volumen-Repräsentativität** (IEX), **Insider-Verzug**. Siehe Spec §11.

## Setup
Wird in Phase 0 etabliert (Python via `uv`). Externe Zugänge (alle kostenlos): Alpaca Paper-Account, SEC-User-Agent-Kontakt, optional Tiingo. Keys nur via `.env` (nie committen).
