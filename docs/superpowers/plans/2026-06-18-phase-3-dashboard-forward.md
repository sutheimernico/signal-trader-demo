# Phase 3 — Dashboard + Forward-Paper Plan

> Source of Truth: `PROJECT.md` §Phase 3. Design: `docs/superpowers/specs/2026-06-17-signal-trader-demo-design.md` §8 (iron principles), §9 (data model), §3/§11 (honesty framing & caveats). Flow: TDD, one task at a time, methodology-review on any code touching point-in-time / costs. Reply German, code/identifiers/commits English.

## Goal

Make the honest measurement harness *observable* and run the plumbing end-to-end: persist `Suggestion` (proposal a user accepts/rejects) and `PaperTrade` (Spec §9), expose them plus per-source hit-rates and **data-lag** through a read API, and extend the Phase-1 Alpaca paper stub into a real (paper-only) order loop. The forward-paper run is **plumbing validation, never a performance claim** (Spec §3, §8.10).

## Scope & sequencing (simplest-first, blocker-isolated)

The phase splits into one **unblocked** backend track and two tracks gated on external/design input:

```
Track A — Backend foundation (UNBLOCKED, build now, fully offline-testable)
  A1  SuggestionStore + PaperTradeStore (SQLite, mirrors SignalStore)        [methodology-review]
  A2  Suggestion builder: consolidated signals -> Suggestion records (PIT)   [methodology-review]
  A3  FastAPI read API: /suggestions, /source-scores, /paper-trades          [api-design-reviewer]
        - serves existing SignalStore/SourceScore + new stores; read-only
  A4  Decision endpoint: POST accept/reject -> updates Suggestion.status

Track B — Alpaca paper loop (BLOCKED: needs paper API keys in .env)
  B1  Extend paper_stub seam: positions, order status, fills polling
  B2  Suggestion(accepted) -> PaperTrade lifecycle, costs/slippage logged honestly
  B3  Live paper smoke (controller-only, never in pytest)

Track C — React 19 dashboard (DESIGN INPUT: Nico's growth area)
  C1  Signal cards, hit-rate table, data-lag column, accept/reject control
  C2  Wires to Track A API
  - Needs a short brainstorming pass on MVP scope + component shape before planning.
```

## Hard dependencies / open inputs (controller)

- **Alpaca paper account + API keys → `.env`** (PROJECT.md open input, unchecked). Track B cannot start until these exist. No live calls ever in pytest.
- **React MVP scope** — Track C needs a brief design decision (which views ship in v1, server-state lib, build tooling). Recommend a `brainstorming` pass before writing C's plan.
- New deps (Track A): `fastapi`, `uvicorn` (pinned). Track C: React 19 toolchain. Announce + pin before adding.

## Iron principles carried in

- **Point-in-time:** `Suggestion.created_at`/`latest_known` from `timestamp_known`; paper entries fill the session after known, never the trade date.
- **Honesty framing:** every dashboard surface and the forward-run is labeled engineering/learning artifact, not edge (Spec §3). Hit-rate from real follow-on results; data-lag always visible (Spec §8.3, §8.4).
- **Costs/benchmark:** paper fills log real costs/slippage; gaps vs. idealized fills surfaced, not hidden (Spec §8.1).
- **No silent truncation; tests offline.**

## Data models (Spec §9)

`Suggestion`: ticker, consolidated_score, contributing_signals (json), created_at, status (open/accepted/rejected), horizon (short/long), user_decision, decided_at, latest_known.

`PaperTrade`: ticker, side, qty, entry_price, entry_time, exit_price, exit_time, pnl, source_suggestion_id.

## This session

Starting Track A1 (SuggestionStore + PaperTradeStore) via TDD — unblocked, unambiguous from spec, reuses the SignalStore pattern verbatim. Tracks B and C wait on the open inputs above.

## Outcome

_(filled as tasks complete)_
