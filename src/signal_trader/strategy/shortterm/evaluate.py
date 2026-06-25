"""Out-of-sample evaluation of the ML experiment (Phase 4).

Honest measurement, not an edge claim. For each PURGED + EMBARGOED walk-forward
fold: fit the forecaster on training rows ONLY, predict the test rows, and on
each test date go long the top-k names by predicted forward return. Every pick's
realized forward return (the point-in-time label) is charged a round-trip cost
(enter + exit). The SAME procedure runs a momentum baseline (top-k by past
return). `beat_baseline` is reported as-is — a model that loses to momentum after
costs is a finding, not something to hide.

Cost note: net = gross - 2*(commission+slippage) per pick (round trip). The
per-rebalance returns are treated as a return series for Sharpe/PSR.

Metric caveat (honest): the rebalances OVERLAP — each label spans the full
horizon, so consecutive rebalances share calendar days. Annualized Sharpe and
the ABSOLUTE PSR (`ml_psr`/`baseline_psr`) are therefore OVERSTATED (serial
correlation, effective sample << n). The only believable figure is the MARGIN
vs the baseline under the SAME folds/costs: `beat_baseline` and `diff_psr` (PSR
of the ml_net-base_net difference). Fix 4 (non-overlapping rebalancing) would
make the absolute numbers trustworthy too; until then, read the margin, not the
levels.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import quantstats as qs

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.metrics import probabilistic_sharpe_ratio
from signal_trader.backtest.validation import purged_walk_forward, sharpe_collapsed
from signal_trader.config import TRADING_DAYS_PER_YEAR
from signal_trader.strategy.shortterm.consensus import ConsensusSignal
from signal_trader.strategy.shortterm.dataset import build_dataset
from signal_trader.strategy.shortterm.model import Forecaster
from signal_trader.strategy.shortterm.survivorship import (
    DelistingEvent,
    apply_delisting_haircut,
)


def _top_k_indices(scores: np.ndarray, k: int) -> np.ndarray:
    return np.argsort(scores)[::-1][:k]


def _top_k_mean(labels: pd.Series, scores: np.ndarray, k: int) -> float:
    return float(labels.iloc[_top_k_indices(scores, k)].mean())


def _lagged_forward_label(
    close_by_ticker: dict[str, pd.Series], horizon: int, extra_lag: int
) -> pd.Series:
    """Forward-return label with ``extra_lag`` more bars of entry delay.

    The unlagged label is ``close[t+1+h]/close[t+1] - 1`` (enter next bar). With
    ``extra_lag=1`` the entry is pushed one bar later: ``close[t+2+h]/close[t+2]
    - 1`` for the SAME decision date ``t``. Indexed by (ticker, date) like
    ``build_dataset`` so it aligns row-for-row onto the feature matrix; rows
    without a full lagged forward window become NaN and are skipped in the
    shift-test series. This is the empirical leak probe: re-realize each pick one
    bar later without changing the pick.
    """
    frames: list[pd.Series] = []
    for ticker, close in close_by_ticker.items():
        entry = close.shift(-(1 + extra_lag))
        exit_ = close.shift(-(1 + extra_lag + horizon))
        lab = (exit_ / entry - 1.0).rename("__label_lagged__")
        lab.index = pd.MultiIndex.from_product(
            [[ticker], lab.index], names=["ticker", "date"]
        )
        frames.append(lab)
    return pd.concat(frames) if frames else pd.Series(dtype=float)


def _sharpe(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 2 or s.std(ddof=1) == 0:
        return 0.0
    return float(qs.stats.sharpe(s, rf=0.0, periods=TRADING_DAYS_PER_YEAR))


def evaluate_ml(
    close_by_ticker: dict[str, pd.Series],
    *,
    horizon: int,
    feature_windows: list[int],
    n_splits: int,
    test_size: int,
    top_k: int,
    cost_model: CostModel,
    forecaster_factory: Callable[[], Forecaster],
    embargo: int = 1,
    consensus_signals: list[ConsensusSignal] | None = None,
    consensus_window_days: int = 30,
    n_configs_tested: int = 1,
    delisting_events: list[DelistingEvent] | None = None,
    delisting_haircut: float | None = None,
) -> dict:
    """Run purged walk-forward OOS evaluation; return an honest scorecard dict.

    The momentum baseline is computed from price momentum alone and never sees
    the consensus column, so the same folds/costs give a fair price-only-vs-+
    consensus A/B: run this twice with and without ``consensus_signals``.

    Two honesty checks are folded in:
    - ``ml_shift_test``: an EMPIRICAL leak probe — re-realize each ML pick one
      bar later (the pick is unchanged) and compare the net-return Sharpe. A
      genuine edge survives; a timing leak collapses. Replaces the purely
      structural ``max(fit)<min(predict)`` argument with measured evidence.
    - ``diff_psr``: PSR of the per-rebalance difference ``ml_net - base_net``
      against 0 — the only margin metric that is not inflated by the bull-market
      regime (the absolute ``ml_psr``/``baseline_psr`` are). ``n_configs_tested``
      is carried through for the deflated-Sharpe / multiple-testing note.

    Survivorship stress (opt-in, default OFF — the ``consensus_signals`` pattern):
    pass ``delisting_events`` + ``delisting_haircut`` to overwrite the realized
    label of any universe name on/after its delisting became knowable with the
    haircut (point-in-time, no lookahead). Both the headline label and the
    shift-test's lagged label are shaded so the two stay coherent; the baseline
    eats the SAME haircut (it ranks the same shaded labels), so the margin stays
    a fair A/B. ``n_delisted_in_universe`` reports how many universe names were
    actually shaded — only names present in BOTH the universe and the delisting
    list can be (the documented partial-correction limit).
    """
    X, y = build_dataset(
        close_by_ticker,
        horizon=horizon,
        feature_windows=feature_windows,
        consensus_signals=consensus_signals,
        consensus_window_days=consensus_window_days,
    )
    y_lagged = _lagged_forward_label(close_by_ticker, horizon=horizon, extra_lag=1)
    y_lagged = y_lagged.reindex(X.index)  # align row-for-row; missing -> NaN

    n_delisted_in_universe = 0
    if delisting_events and delisting_haircut is not None:
        universe_tickers = set(X.index.get_level_values("ticker").unique())
        in_universe = [e for e in delisting_events if e.ticker in universe_tickers]
        n_delisted_in_universe = len({e.ticker for e in in_universe})
        # Shade both labels so the shift-test sees the same stressed picks.
        y = apply_delisting_haircut(y, in_universe, delisting_haircut)
        y_lagged = apply_delisting_haircut(y_lagged, in_universe, delisting_haircut)
    date_level = X.index.get_level_values("date")
    dates = pd.Index(sorted(date_level.unique()))
    folds = purged_walk_forward(
        dates, n_splits=n_splits, test_size=test_size, horizon=horizon, embargo=embargo
    )
    round_trip = 2.0 * (cost_model.commission_per_trade + cost_model.slippage)
    mom_col = f"ret_{max(feature_windows)}"

    ml_gross: list[float] = []
    ml_net: list[float] = []
    base_net: list[float] = []
    # Paired sub-sample for the shift-test: unlagged vs lagged net return of the
    # SAME picks, kept ONLY for rebalances whose +1-bar-lagged forward window is
    # fully formed — so the two Sharpes are compared over the identical sample.
    shift_unlagged: list[float] = []
    shift_lagged_net: list[float] = []
    for train_dates, test_dates in folds:
        train_mask = date_level.isin(train_dates)
        if not train_mask.any():
            continue
        model = forecaster_factory()
        model.fit(X[train_mask], y[train_mask])
        for d in test_dates:
            rows = X[date_level == d]
            if len(rows) < top_k:
                continue
            labels = y.loc[rows.index]
            preds = np.asarray(model.predict(rows), dtype=float)
            picks = _top_k_indices(preds, top_k)
            ml = float(labels.iloc[picks].mean())
            base = _top_k_mean(labels, rows[mom_col].to_numpy(), top_k)
            ml_gross.append(ml)
            ml_net.append(ml - round_trip)
            base_net.append(base - round_trip)
            # Empirical shift-test: the identical picks, re-realized one bar later.
            lagged = y_lagged.loc[rows.index].iloc[picks]
            if not lagged.isna().any():
                shift_unlagged.append(ml - round_trip)
                shift_lagged_net.append(float(lagged.mean()) - round_trip)

    n = len(ml_net)
    ml_series = pd.Series(ml_net, dtype=float)
    base_series = pd.Series(base_net, dtype=float)
    diff_series = ml_series - base_series
    ml_mean = float(ml_series.mean()) if n else 0.0
    base_mean = float(base_series.mean()) if n else 0.0

    shift_baseline = _sharpe(pd.Series(shift_unlagged, dtype=float))
    shift_lagged = _sharpe(pd.Series(shift_lagged_net, dtype=float))
    return {
        "n_rebalances": n,
        "ml_mean_gross": float(np.mean(ml_gross)) if ml_gross else 0.0,
        "ml_mean_net": ml_mean,
        "baseline_mean_net": base_mean,
        "ml_psr": probabilistic_sharpe_ratio(ml_series) if n > 2 else 0.0,
        "baseline_psr": probabilistic_sharpe_ratio(base_series) if n > 2 else 0.0,
        # Robust margin: PSR of the ML-minus-baseline difference vs 0. <0.5 means
        # the difference Sharpe is <=0, i.e. ML does not robustly beat baseline.
        "diff_psr": probabilistic_sharpe_ratio(diff_series) if n > 2 else 0.0,
        "ml_shift_test": {
            "baseline": shift_baseline,
            "shifted": shift_lagged,
            "collapsed": sharpe_collapsed(shift_baseline, shift_lagged),
        },
        "n_configs_tested": n_configs_tested,
        "delisting_haircut": delisting_haircut,
        "n_delisted_in_universe": n_delisted_in_universe,
        "beat_baseline": bool(ml_mean > base_mean),
    }
