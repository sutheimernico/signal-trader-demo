# Phase 4 — ML Experiment (Track 2, autonomous paper) Plan

> Source of Truth: `PROJECT.md` §Phase 4. Locked decisions (`CLAUDE.md`): **no LLM price prediction** (knowledge-cutoff contaminated — forbidden), GBDT default (LightGBM), **purged + embargoed** walk-forward, must beat the momentum baseline **after costs**, paper-only. TDD, methodology-review every feature/label/CV step. Reply German, code English.

## Goal

An **autonomous** ML experiment that runs in the **paper** track (no human confirmation): from the cached point-in-time price bars, build leakage-safe features + forward-return labels, train a GBDT, evaluate under purged/embargoed walk-forward **after costs against the momentum baseline**, and — only if it clears that bar honestly — let it place paper orders by itself. It is a measurement experiment, never an edge claim; a model that fails to beat the baseline is reported as such, not hidden.

Separation from Track 1 (locked with Nico, 2026-06-18): **Insider suggestions = human-facing**, acting on them is a manual user decision outside the app; the app never executes real orders. **ML = automated paper only.** The two never cross.

## Hard guardrails (non-negotiable)

- **No LLM / no look-ahead text.** Features come only from the bar cache, point-in-time.
- **Label leakage forbidden:** features at decision time `t` use only data `≤ t`; the label is the forward return over `t+1 … t+h`. Entry is the bar AFTER the signal (reuse the Phase-1 PIT rule).
- **Purged + embargoed walk-forward:** drop training samples whose label window overlaps the test window (purge) plus an embargo gap, so no leakage across the fold boundary. This is the single biggest overfitting/leakage risk and gets a dedicated methodology review.
- **After costs, vs baseline, PSR.** Reuse Phase-1 `costs`, `metrics`, `benchmark`. A model is "better" only if it beats `momentum_signals` after the SAME costs on OOS folds.
- **No silent truncation; tests offline; LightGBM behind an interface, faked in tests.**

## Tech

New dep (sanctioned by PROJECT.md stack): `lightgbm` (pinned). Reuses Phase-1 `backtest/{costs,metrics,benchmark,validation,result}` and the cache. Cross-sectional, short-horizon forward-return regression → long the top-ranked names.

## Tasks (TDD, one at a time)

1. **Dataset builder** `strategy/shortterm/dataset.py` — bars → (X features, y forward-return) per (ticker, date), strictly point-in-time. Features: multi-window returns, volatility, momentum, volume z-score — all from data `≤ t`. Label: `close[t+h]/close[t+1] − 1` (entry next bar, PIT). Rows without a full forward window are dropped, never zero-filled. **[methodology-review]**
2. **Purged + embargoed walk-forward** `backtest/validation.py` (extend) — `purged_walk_forward(index, n_splits, test_size, horizon, embargo)` returning (train_idx, test_idx) with label-overlap purge + embargo. **[methodology-review]**
3. **Model seam** `strategy/shortterm/model.py` — `Ranker` protocol + `LGBMRanker` impl; faked in tests. fit(X_train, y_train) / predict(X_test).
4. **OOS evaluation** `strategy/shortterm/evaluate.py` — train/predict per fold, build long-top-k positions, run through an engine after costs, compare to momentum baseline + PSR. Reports honestly (incl. "did not beat baseline"). **[methodology-review]**
5. **Autonomous paper hook** `paper/ml_loop.py` — predictions → paper orders via the Broker seam, no confirmation. Offline-tested with a fake broker.
6. **CLI** `scripts/run_ml_experiment.py` — train → evaluate → (optional) paper-trade; prints the honest scorecard.

## This session

Task 1 (dataset builder) — the leakage surface that everything else depends on.

## Outcome

_(filled as tasks complete)_
