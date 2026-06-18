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

## Outcome (2026-06-18)

**Track A (backend foundation) — COMPLETE.** 149 tests pass, ruff clean, all offline.
- A1 `feat(store): Suggestion and PaperTrade persistence with integrity guards` — SQLite stores mirroring SignalStore; added rowcount guards (close_trade raises on double-close/unknown id; record_decision raises on lost decision) after methodology review flagged silent-overwrite risks for the forward run.
- A2 `feat(signals): build point-in-time Suggestions from consolidated signals` — reuses consolidate_per_ticker; created_at == latest_known (PIT), idempotent re-run.
- A3+A4 `feat(api): FastAPI read endpoints + suggestion decision` — GET /suggestions (?status), /source-scores (data-lag always visible), /paper-trades (?open_only); POST decision. After api-design-review: 422 on malformed date (was 422-vs-404 confusion), contributing_signals returned as parsed object, decision constrained to Literal[accepted,rejected].
- New deps (spec-mandated): `fastapi==0.137.2`, `uvicorn==0.49.0`, pinned; uv.lock updated.

**Track B (forward paper loop) — OPEN-bridge done, live adapter blocked.**
- `feat(paper): broker seam + forward loop opening trades from accepted suggestions` — `paper/broker.py` (Broker Protocol + Fill), `paper/loop.py` (open_accepted_suggestions). Accepted suggestions → opened PaperTrades from the ACTUAL broker fill (no idealized price, Spec §8.1), idempotent, PIT-safe. Offline-tested with a fake broker.
- After methodology review: added `UNIQUE(source_suggestion_id)` DB backstop against double-open, and per-suggestion log+skip so one rejected order doesn't abort the rest.
- **Still blocked:** live alpaca-py adapter conforming to `Broker` (fill polling) needs paper API keys in `.env`; never in pytest. The **close/exit path** (hold rule → close_trade with exit fill) is the next backend piece but needs a deliberate exit-rule + exit-price-source decision (cached close vs. live poll) — a methodology choice, not improvised.

**Design brief for the UI:** `docs/design/2026-06-18-dashboard-design-brief.md` — self-contained, hand to Claude Design/Artifacts to generate Track C.

**Track C (React 19 dashboard)** — design brief written; needs Nico to run it through a design tool / decide MVP scope. Wires to the Track A API now standing.

**Not done / deferred decisions (api-design-review, proportionate to local single-user scope):** Pydantic response_models (skipped for now — would improve OpenAPI), 204-vs-200 + 409 on idempotent re-decision, decided_at as date (store contract; loses intra-day ordering — fine for paper demo).
