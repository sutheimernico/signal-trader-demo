# Session — Phase 1 Foundation complete

**Date:** 2026-06-17 · **Branch:** `feat/phase-1-foundation` (merged to `main`)

## Context
First working session on `signal-trader-demo`. Took the user's draft trading-demo plan, critiqued it, researched best practices (3 deep dives: backtest methodology, signal sources, ML/LLM reality), reframed the project as an **honest measurement harness** (no edge promise — research-backed), scaffolded the repo in the prior-projects convention, and built Phase 1 end to end.

## What was done
- **Conception:** `PROJECT.md` (source of truth), `docs/superpowers/specs/2026-06-17-...-design.md`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `.claude/agents/backtest-methodology-reviewer.md`.
- **Skill installed:** `marketcalls/vectorbt-backtesting-skills@backtest` (audited, on-stack).
- **Phase 1 (13 tasks, TDD, subagent-driven):** provider seam (yfinance) → Parquet/SQLite cache (range-aware, no silent truncation) → cost model → momentum baseline (one-bar leakage shift) → two engines (vectorbt + backtesting.py) → metrics (CAGR/Sharpe/Sortino/Calmar/MaxDD + custom PSR) → after-cost benchmark → shift-test/OOS/walk-forward → break-even check → Alpaca paper stub (mocked) → CLI + foundation report.
- **71 tests pass, ruff clean.** Live smoke (AAPL) renders the report; momentum honestly underperforms buy-and-hold after costs.

## Key decisions / findings
- Two methodology gates caught **real invalidating bugs**: the shift-test was a no-op (couldn't detect same-series lookahead) and CAGR/Calmar were understated ~29%. Both fixed and proven (commit `8eadaf0`).
- Momentum baseline is state-based, not crossover (plan's crossover code contradicted its own tests).
- The vectorbt-vs-backtesting.py gap is real but data-dependent, not a guaranteed direction.
- Full outcome + deviations: see Implementation Notes in `docs/superpowers/plans/2026-06-17-phase-1-foundation.md`.

## Open questions / to-dos (Phase 2 and inputs)
- **Open Inputs (Nico owns):** Alpaca paper keys + SEC identity → `.env`; optional Tiingo key; git remote/visibility before any push (currently local-only, no remote).
- **Phase 2:** insider-cluster-buy signals (SEC Form 4 via `edgartools`; filters: opportunistic + code "P" + cluster + small-cap), consolidation, hit-rate logging.
- **Carried nits:** add nullable `adj_close` column (Tiingo upgrade); expose walk-forward params in CLI; surface data-lag/hit-rate in UI (Phase 3).

## Next session entry point
Phase 2 starts from the consolidated signal layer. Re-run `brainstorming`/`writing-plans` for Phase 2 scope, or extend the existing spec. The harness (cache + engines + honest metrics + validation) is ready to receive real signals.
