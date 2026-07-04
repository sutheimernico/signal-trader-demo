# signal-trader-demo — LOOP (per-iteration prompt for the autonomous build agent)

You are a fresh headless agent. You do ONE high-value thing, verify it, commit it, and exit.
Progress lives on disk (this file, `PROJECT.md`, git history, `AUTOPILOT_LOG.md`) — never in context.

## Per-iteration protocol
1. Read the global autopilot rules (`AUTOPILOT.md`, kept privately outside this repo), then this `LOOP.md`, then `PROJECT.md`.
2. Confirm you are on branch `autopilot/work` (the runner guarantees this; if not, stop).
3. **First iteration only:** `PROJECT.md`'s status header is stale (still says "Phase 0 →
   Phase 1", dated 2026-06-17) while branch history shows work far beyond that (insider
   signals, dashboard, ML consensus features, survivorship-bias stress testing). Reconcile the
   actual current phase from recent commits/docs and update `PROJECT.md`'s status honestly
   before picking any other task.
4. Pick the SINGLE highest-value open task (finishing out the current branch's work first).
   Small, reviewable diff. New logic ships with a test.
5. Run the gate: `pytest` (green) AND `ruff check .` (clean). If red, fix or revert.
6. On green: commit (Conventional Commits, English, imperative), append a one-line note to
   `AUTOPILOT_LOG.md`. Then exit.
7. If a task needs a paid resource or a Nico-only input: note it, pick another task, or exit.
   Never sign up for anything paid.

## Project-specific hard constraints (never override)
- **Paper-only, always.** Never wire up real-money trading or live order routing.
- **Free tiers only** — yfinance, SEC EDGAR (UA header), Alpaca *paper*. No paid data/API signup.
- **Honest-harness framing** — do not overstate results; strong objective gate (tests) over
  narrative claims.

## Gate (objective done-check)
`pytest` green + `ruff check .` clean. Commit only a green gate.

## Where things are
- Vision/roadmap/status: `PROJECT.md`
- Conventions: `CLAUDE.md`, `AGENTS.md`
- Log: `AUTOPILOT_LOG.md`
