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

## Insider/congress/fund consensus feature (2026-06-25, autonomous)

Added an **opt-in, point-in-time** consensus feature (`strategy/shortterm/consensus.py`,
wired into `build_dataset`/`evaluate_ml`/`run_ml_experiment.py` behind `--consensus`,
default OFF — the `_add_calendar` opt-in pattern): per `(ticker, t)`, the count of
**distinct buyers** (insider/congress/fund, keyed by `(source, accession_no)`) whose
`timestamp_known` falls in `(t − window, t]`. As-of join on `timestamp_known` only
(never `timestamp_event`); missing = explicit 0 over existing price rows (no fabricated
/dropped rows). Leak surface covered by offline fixture tests (as-of leak, missing→0,
determinism, no cross-ticker bleed); methodology review found nothing invalidating;
baseline (`mom_col`) never sees the consensus column, so the *margin* is a fair A/B —
but note the absolute PSR is overstated (overlapping horizons, below), so only the
margin vs baseline is believable, not the levels.

**Honest OOS A/B** (local cache, GBDT, SAME purged+embargoed walk-forward, after costs;
universe = 239 names that have BOTH signals and bars, 2025-01..2026-06, horizon 5,
top-k 3, 4 folds → 84 OOS rebalances). Re-run 2026-06-25 with the two sharper
honesty metrics (diff-PSR, shift-test):

| window | ML net/rebal | abs PSR ⚠ | Δ vs price-only | **diff-PSR** | **beats baseline?** |
|--------|-------------|-----------|-----------------|--------------|---------------------|
| 30d | +0.02226 | 0.992 | +0.00297 ⚠ | 0.161 | **No** |
| 90d | +0.02169 | 0.990 | +0.00239 ⚠ | 0.113 | **No** |
| 180d | +0.01448 | 0.952 | −0.00481 | 0.016 | **No** |

price-only ML: **+0.01930**/rebal, abs PSR 0.982 ⚠, diff-PSR **0.056**, beats baseline **No**.
Momentum baseline: **+0.03399**/rebal (abs PSR 1.000).

- **The "beats baseline?" column is the ONLY load-bearing figure.** ⚠ = inflated /
  not believable on its own: the absolute PSRs (~0.95–1.0) are a bull-market artifact
  (see overlapping-horizon caveat), and the `Δ vs price-only` at 30/90d is a rosinen-
  pick trap — those `+0.003`/`+0.002` improvements sit on the 1.6%-sparse feature
  (next bullet) and **flip sign to −0.005 at 180d**, so the "help" is a window-hyper-
  parameter artifact, not a stable signal (the same trap the calendar-feature lesson
  flagged). Do not read the Δ without the sparsity caveat attached.
- **diff-PSR confirms it quantitatively:** PSR of the per-rebalance `ml_net − base_net`
  difference vs 0 is **< 0.5 in every arm** (0.016–0.161) — i.e. the difference Sharpe
  is ≤ 0, ML does not robustly beat momentum after costs. This is the believable margin
  metric; the absolute `ml_psr` is not.
- **Shift-test (empirical leak probe, 2026-06-25):** re-realizing the SAME ML picks one
  extra bar later does **NOT collapse** the net-return Sharpe in any arm (e.g. price-only
  3.70 → 4.55; 180d 2.86 → 3.87; `collapsed=False` throughout). Read this honestly: it
  is **not** a clean bill of health — there is barely an edge to collapse (ML loses to
  baseline), so the shift-test is weakly diagnostic here. The Sharpe even nudges *up*
  under the lag, which is noise on overlapping, regime-driven returns (every pick rides
  the same bull drift; one bar of offset barely moves it). The structural leak guard
  (`max(fit)<min(predict)` per fold + purge/embargo) remains the real protection; the
  shift-test simply finds no *additional* timing leak to flag.
- **Why the data can't say more (honest limits):** the feature is extremely sparse —
  only **1.6%** of rows are non-zero and almost all of those equal 1 (17 rows = 2), and
  the underlying signals cluster in **2026-05**. At top-k 3 over 239 names the consensus
  column moves the picks on only a handful of dates, so 84 rebalances over one
  bull-market window is too thin to claim either way.
- **Overlapping-horizon caveat:** rebalances overlap by default (each label spans the full
  horizon, consecutive rebalances share calendar days), so annualized Sharpe and the
  absolute PSR are overstated (serial correlation, effective n ≪ 84). **Fix 4 landed
  2026-07-01** as an opt-in flag (`evaluate_ml(..., non_overlapping=True)`, CLI TBD):
  strides test dates by `horizon` bars so no two rebalances share a holding period,
  making the absolute PSR/Sharpe trustworthy at the cost of ~horizon-times fewer
  rebalances. Default stays OFF (dense/overlapping, margin-only reading unchanged) so
  existing reported numbers are not silently altered. Honest limit: the stride phase is
  fixed at each fold's first test date (not randomized/rotated), applied identically to
  ML and baseline so the margin stays fair, but not stress-tested across phase offsets.
- **Deflated-Sharpe note (multiple testing):** the +consensus arm was selected over **3
  windows** (30/90/180d); with several configs tested the absolute PSR overstates
  significance. At the time, no formal DSR gate was applied — `evaluate_ml` carried a
  manually-typed `n_configs_tested` that nothing ever actually populated (the CLI always
  left it at its default of 1, so the printed note was honest about the RISK but not
  about the REAL count).

  **Landed 2026-07-02:** a full Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014),
  `backtest/metrics.{expected_max_sharpe,deflated_sharpe_ratio}`, tested against the
  paper's own worked numeric example (SR=2.5 annualized, Var[SR]=0.5, 100 trials, 1250
  days, skew=-3, kurtosis=10 -> DSR≈0.8997, independently re-derived from the paper's
  formula). The manual `n_configs_tested` knob is gone, replaced by
  `backtest/trial_log.py` — an append-only local log that every `run_backtest.py` /
  `run_ml_experiment.py` invocation writes one trial to (per-period Sharpe + config
  label), so DSR is computed from the ACTUAL trial history instead of a guess. Both
  CLIs now print `DSR=` next to `PSR=` and the real trial count. Simplification, stated
  rather than hidden: all runs of one CLI share a single trial "family" regardless of
  which flags were set (e.g. `--consensus` on/off) — a stricter DSR would split
  families per flag combination.
- **What a real test would need (Needs Nico):** a denser, longer point-in-time signal
  history (multi-year Form-4/13F/congress backfill, not the current ~250 mostly-2026
  rows) and window selection done INSIDE the purged CV. Non-overlapping rebalancing
  (Fix 4) is now available (see above) but was not re-run for this consensus A/B — with
  today's cache the feature is plumbing-validated and leakage-safe, but the A/B remains
  underpowered regardless of rebalancing mode.

## FREE synthetic-delisting survivorship stress test (2026-06-26, autonomous)

Converts the ML claim from "edge in a bull market" toward "does the result survive
survivorship scrutiny?" — for free, no paid feed. The earlier `--broad` check
admitted the universe is still survivors-only (yfinance serves no delisted prices),
so this is the adversarial complement.

**Mechanism (leakage-safe, opt-in, default OFF — the `--consensus` pattern):**
- `strategy/shortterm/survivorship.py` — `DelistingEvent(ticker, delisted_known)` +
  `apply_delisting_haircut(y, events, haircut)`: overwrite the realized forward-return
  label of any universe name on/after its delisting became KNOWABLE (`delisted_known`,
  the SEC filing date — never the event date) with a pessimistic haircut. Point-in-time,
  no lookahead; labels overwritten, never fabricated/dropped; earliest record governs.
- `market_data/delistings.py` — FREE delisting list from SEC EDGAR full-text search
  (Form 25-NSE/25; ticker in `display_names`, filing date = knowable date). Offline-first:
  eval/CLI read a cached CSV (`data/delistings.csv`); `fetch_delistings` is the only
  network path, behind an injected `http_get` (stdlib urllib in prod, faked in tests —
  no live SEC call in pytest), SEC fair-access UA mandatory, throttled <10 req/s.
  `scripts/ingest_delistings.py` refreshes the cache (controller-only, like `sec_smoke.py`).
- `evaluate_ml(..., delisting_events, delisting_haircut)` shades both the headline and
  the shift-test's lagged label so they stay coherent; the momentum baseline ranks the
  SAME shaded labels, so the margin stays a fair A/B. Scorecard carries
  `n_delisted_in_universe` + `delisting_haircut`. CLI: `--survivorship-stress`
  `--delisting-haircut`.

**Honest measured result** (local ml_cache, 108 names, 2013–2026, GBDT, SAME
purged+embargoed walk-forward, horizon 5, top-k 3, 4 folds → 252 OOS rebalances,
14 real severe decliners shaded point-in-time):

| run | ML net/rebal | baseline net/rebal | diff-PSR | beats baseline? |
|---|---|---|---|---|
| survivors-only | +0.00875 | +0.01350 | 0.104 | No |
| stress −0.40 | −0.01785 | −0.11864 | 1.000 | **Yes** |
| stress −0.60 | −0.02039 | −0.18161 | 1.000 | **Yes** |
| stress −1.00 | −0.01264 | −0.30753 | 1.000 | **Yes** |

**Interpretation (the honest reading — do NOT spin this as an ML edge):** "ML beats
baseline under stress" is NOT "ML has alpha". Both LOSE money under stress (ML net is
still negative everywhere). The driver is **baseline fragility**: the momentum baseline
picks a shaded (fragile) decliner **31.5 %** of the time (it chases their momentum
spikes), the GBDT only **3.3 %** (−0.60 haircut). So the GBDT is structurally less
survivorship-fragile than naive momentum — a real, measured finding, not an edge claim.
(Survivors-only, ML still loses to momentum: the prior honest result is unchanged.)
These pick rates are emitted by `evaluate_ml` (`ml_shaded_pick_rate` /
`baseline_shaded_pick_rate`) and printed by the CLI, so the load-bearing figure is
reproducible from code, not hand-computed.

**Methodology-review fix (folded in):** the shift-test sample is gated on the
PRE-haircut formed mask — shading changes the lagged values but never which rebalances
qualify, so a shaded NaN row cannot slip into the leak probe only under stress (which
would have weakened it in the flattering direction). The measured table above is
unchanged by the fix.

**Honest limits (documented, not hidden):** PARTIAL & conservative correction — only
names in BOTH the survivor universe AND the free delisting list can be shaded; the bulk
of delisted names are simply absent and unrecoverable without paid delisted prices
(**CRSP/Sharadar/Norgate — Needs Nico**). Form 25 mixes M&A/voluntary delistings with
bankruptcy, so a shaded name "left the listing", not "went bankrupt". The haircut is a
transparent assumption → a sensitivity band (−0.40/−0.60/−1.00), not one magic number.
