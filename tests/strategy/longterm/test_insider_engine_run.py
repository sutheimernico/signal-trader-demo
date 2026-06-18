import datetime as dt

import numpy as np
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.validation import shift_test
from signal_trader.store.signal_store import StoredSignal
from signal_trader.strategy.longterm.insider_strategy import (
    insider_entries_exits,
    run_insider_through_engines,
)

_COST = CostModel(commission_per_trade=0.001, slippage=0.0005)


def _close():
    idx = pd.date_range("2024-01-01", periods=120, freq="B")
    return pd.Series([100.0 + i * 0.5 for i in range(120)], index=idx)


def _signals(close):
    return [
        StoredSignal(
            ticker="AAPL", source="insider_form4",
            signal_type="insider_cluster_purchase", direction="long",
            timestamp_event=dt.date(2024, 1, 1),
            timestamp_known=close.index[d].date(), price_at_known=100.0,
            raw_payload_json="{}", confidence=0.6,
        )
        for d in (10, 40, 70)
    ]


def test_both_engines_run_and_agree_on_trade_count():
    close = _close()
    results = run_insider_through_engines(close, _signals(close), _COST, hold_bars=5)
    assert set(results) == {"vectorbt", "backtesting.py"}
    assert results["vectorbt"].n_trades == results["backtesting.py"].n_trades
    assert (results["vectorbt"].equity_curve > 0).all()


def _volatile_close():
    # shift_test is vacuous on a monotonic series (returns never change sign);
    # a noisy series is required for it to discriminate leaky from clean signals.
    idx = pd.date_range("2024-01-01", periods=120, freq="B")
    rng = np.random.default_rng(42)
    rets = pd.Series(rng.normal(0.0005, 0.02, 120), index=idx)
    return pd.Series(100.0 * (1.0 + rets).cumprod().to_numpy(), index=idx)


def test_shift_test_discriminates_leaky_from_pit_insider_signal():
    # shift_test detects CONTEMPORANEOUS leakage (signal using same-bar info),
    # not PIT-cleanness directly — PIT entry timing is covered by
    # test_entry_fires_on_bar_strictly_after_known. Here we prove the harness
    # discriminates: a signal built from the same-bar return sign collapses
    # under the extra lag, while the PIT insider position (entries placed
    # strictly after the filing date) does not.
    close = _volatile_close()
    returns = close.pct_change().fillna(0.0)

    leaky = np.sign(returns)  # uses the bar's own return -> contemporaneous leak
    assert shift_test(leaky, returns)["collapsed"] is True

    entries, _ = insider_entries_exits(close, _signals(close), hold_bars=5)
    insider_position = entries.astype(float)
    assert shift_test(insider_position, returns)["collapsed"] is False
