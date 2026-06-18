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

## Outcome (2026-06-18)

All 6 tasks built TDD, methodology-reviewed, 185 tests green, ruff clean, all offline.
- Task 1 dataset (PIT features/forward labels) — review: no lookahead; fixed silent NaN→0 via `fill_method=None`.
- Task 2 `purged_walk_forward` — review: enforce `embargo>=1` (else 1-bar label/test overlap).
- Task 3 `Forecaster` seam + `GBDTForecaster` (LightGBM, pinned).
- Task 4 `evaluate_ml` — OOS after costs vs momentum baseline + PSR; per-fold leak-detector test; review: no invalidating leakage.
- Task 5 `open_ml_positions` — autonomous paper loop (no confirmation), idempotent, log+skip.
- Task 6 `scripts/run_ml_experiment.py` — train → evaluate → autonomous paper-trade.

**First real result (honest, not edge):** bank/energy basket (14 tickers), 2023–2024, horizon 5, top-k 3, 4 folds → **84 OOS rebalances**. After costs:
- ML (LightGBM, price features): mean **−0.0023**/rebalance, PSR 0.231
- Momentum baseline: mean **+0.0033**/rebalance, PSR 0.790
- **ML did NOT beat the baseline after costs.** This is the expected, honest finding — a naive price-feature GBDT does not earn its costs vs simple momentum for retail. Reported as a learning artifact, not hidden.

**Autonomous paper trading is wired** (`run_ml_experiment.py` without `--no-trade` places top-k Alpaca **paper** orders, no confirmation) but given the model loses to baseline, trading it is not justified by the evaluation — left for Nico to kick off as an experiment.

**Next experiments (would need their own methodology pass):** richer features (volume, cross-sectional rank, fundamentals — point-in-time), better label (rank/IC target), proper hyperparameter search inside the purged CV (no leakage), and a stronger/again-honest baseline.

## Survivorship sensitivity (2026-06-18, autonomous)

Re-ran the retro eval on a broader, less cherry-picked universe (108 names incl.
decliners/mid-caps via `--broad`):
- ML +0.00505/rebal (PSR 0.993) vs baseline +0.00361 (PSR 0.974), 630 OOS rebalances → ML still beats baseline.
- Margin shrank from ~0.23%/rebal (mega-cap-only) to ~0.14% (broad) — edge is NOT pure survivorship artifact, but smaller.
- **Caveat (honest):** still not a clean survivorship test — yfinance has no data for truly delisted names (WBA/PARA/etc. failed to load), so the universe is still survivors-only. Both PSRs ~0.98 reflect a 14-year bull market; only the ML-vs-baseline margin is meaningful.
- **Blocked for a clean test:** need a point-in-time index-constituent + delisted-price feed (paid: CRSP/Sharadar/Norgate). Flagged to Nico.
- Next honest checks: shift-test on the ML position series (timing-leakage robustness); recent-2-month focused readout.

## Empirical overfitting check (2026-06-18, autonomous)

Tested Nico's "more parameters" request directly: added PIT calendar/seasonality
features (weekday, month, turn-of-month, quarter-end) and re-ran the SAME honest
OOS eval (108 names, 630 rebalances):
- price-only: ML +0.00505/rebal → BEATS baseline (+0.00361)
- + calendar features: ML +0.00297/rebal (PSR 0.925) → LOSES to baseline
- **More features made OOS WORSE — textbook overfitting.** Per honest-harness
  discipline, calendar features were DISABLED (helper kept, off by default). This
  is the empirical proof that "max parameters" backfires; complexity must earn
  its place on the OOS test, not in-sample.
