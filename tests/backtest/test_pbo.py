import math

import numpy as np
import pandas as pd
import pytest

from signal_trader.backtest.pbo import probability_of_backtest_overfitting


def _noise_frame(n_periods=320, n_strategies=6, seed=1):
    """N strategies with IDENTICAL return distributions (pure noise, no real
    differences) — any one being IS-best is a coin flip on OOS rank."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_periods, freq="B")
    data = rng.normal(0.0, 0.01, size=(n_periods, n_strategies))
    return pd.DataFrame(data, index=idx, columns=[f"cfg_{i}" for i in range(n_strategies)])


def _one_dominant_strategy_frame(n_periods=320, n_strategies=6, seed=2):
    """One strategy has a real, consistent edge over the others in EVERY
    period (not just on average) — it must win both IS and OOS every split."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_periods, freq="B")
    data = rng.normal(0.0, 0.005, size=(n_periods, n_strategies))
    data[:, 0] += 0.01  # cfg_0 dominates in every single period
    return pd.DataFrame(data, index=idx, columns=[f"cfg_{i}" for i in range(n_strategies)])


def test_pbo_near_half_for_indistinguishable_strategies():
    result = probability_of_backtest_overfitting(_noise_frame(), n_blocks=8)
    assert 0.3 <= result.pbo <= 0.7


def test_pbo_near_zero_for_one_dominant_strategy():
    result = probability_of_backtest_overfitting(_one_dominant_strategy_frame(), n_blocks=8)
    assert result.pbo < 0.15


def test_n_combinations_matches_binomial_coefficient():
    result = probability_of_backtest_overfitting(_noise_frame(), n_blocks=8)
    assert result.n_combinations == math.comb(8, 4)
    assert len(result.logits) == result.n_combinations


def test_rejects_odd_n_blocks():
    with pytest.raises(ValueError):
        probability_of_backtest_overfitting(_noise_frame(), n_blocks=7)


def test_rejects_fewer_than_two_strategies():
    frame = _noise_frame(n_strategies=1)
    with pytest.raises(ValueError):
        probability_of_backtest_overfitting(frame, n_blocks=8)


def test_rejects_too_few_observations_for_block_count():
    frame = _noise_frame(n_periods=4)
    with pytest.raises(ValueError):
        probability_of_backtest_overfitting(frame, n_blocks=8)


def test_default_n_blocks_is_sixteen_per_the_paper():
    # Small N/T so the (16 choose 8) = 12,870 combinations stay fast in CI.
    result = probability_of_backtest_overfitting(_noise_frame(n_periods=320, n_strategies=3))
    assert result.n_combinations == math.comb(16, 8)
