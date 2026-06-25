# signal-trader-demo — autopilot log

One line per iteration. Newest last.

- 2026-06-26 — Gate already fully green (218→238 tests, ruff clean); the prompt's "~196/218" was stale. Built the FREE synthetic-delisting survivorship stress test (Phase 4 headline): `survivorship.py` (point-in-time haircut), `delistings.py` (SEC Form 25/25-NSE FTS, offline-first cache, network behind injected seam), `evaluate_ml` opt-in + CLI `--survivorship-stress`/`--delisting-haircut`, `ingest_delistings.py`. Measured on local 108-name cache (252 OOS reb): survivors-only ML loses to momentum (diff-PSR 0.10); under −0.40/−0.60/−1.00 haircut ML "beats" baseline (diff-PSR 1.0) — but the honest reading is BASELINE FRAGILITY (baseline picks shaded decliners 31.5% vs ML 3.3%), both lose money, NOT an ML edge. README + Phase-4 plan updated with the artifact + honest limits (paid CRSP = Needs Nico). On branch feat/survivorship-stress-test.
