"""Probability of Backtest Overfitting (PBO) via Combinatorially Symmetric
Cross-Validation (CSCV) — Bailey, Borwein, Lopez de Prado & Zhu (2015), "The
Probability of Backtest Overfitting".

PSR/DSR (metrics.py) ask "is THIS one result significant". PBO asks the
complementary question a parameter/strategy SEARCH needs answered: "if I
pick the best of these N candidate configs by their in-sample performance,
how likely is that 'best' pick to actually be below-median out-of-sample?"
— i.e. how much of the apparent outperformance is just picking whichever
config happened to fit this data's noise (overfitting), rather than a config
that is genuinely, transferably better.

Algorithm (CSCV): split the T periods into ``n_blocks`` equal contiguous
blocks (even, so they split symmetrically). For every way of choosing half
the blocks as the "in-sample" (IS) set and the other half as "out-of-sample"
(OOS) — C(n_blocks, n_blocks/2) combinations — rank all N strategies by
their IS Sharpe, take the IS-best one, and find ITS OOS rank. Convert that
relative OOS rank to a logit; PBO is the fraction of combinations where the
logit is <= 0, i.e. the IS-best strategy performed at or below the OOS
median — evidence that picking "the best backtest" would not have picked a
genuinely better strategy.

This deliberately does not have a single canonical Python reference
implementation to copy from; the tests here instead check the two
properties the paper's own experiments demonstrate: PBO ~ 0.5 for a set of
strategies with no real differences (pure noise — being IS-best is a coin
flip on OOS rank) and PBO ~ 0 for a set where one strategy has a real,
consistent edge over the others in both halves.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PBOResult:
    pbo: float  # fraction of CSCV splits where the IS-best strategy was OOS-below-median
    n_combinations: int  # how many (train, test) block partitions were evaluated
    logits: list[float]  # the raw logit(omega_c) per combination, for a rank histogram


def probability_of_backtest_overfitting(
    returns: pd.DataFrame, n_blocks: int = 16
) -> PBOResult:
    """Compute PBO for a matrix of candidate strategies/configs.

    ``returns``: T x N DataFrame, one column per strategy/config trial (e.g.
    different lookback windows), one row per period, ALREADY after costs.
    ``n_blocks`` must be even (the paper's own examples use 16 by default);
    the number of CSCV combinations is C(n_blocks, n_blocks/2), which grows
    fast (16 -> 12,870 — the cost of an honest overfitting check). The loop
    body works on plain numpy arrays (no pandas/concat per iteration); at
    16 blocks this keeps the whole check to low single-digit seconds instead
    of the ~50s a naive pandas-per-combination version costs.
    """
    if n_blocks % 2 != 0:
        raise ValueError("n_blocks must be even for CSCV's symmetric train/test split")
    if returns.shape[1] < 2:
        raise ValueError("need at least 2 strategies/trials to rank")

    n_strategies = returns.shape[1]
    values = returns.to_numpy(dtype=float)
    t = len(values)
    block_size = t // n_blocks
    if block_size < 1:
        raise ValueError(
            f"need at least {n_blocks} observations for {n_blocks} blocks, got {t}"
        )
    # Trailing rows that don't fill a full block are dropped: CSCV needs
    # equal-sized blocks so every combination sums the same period count.
    blocks = values[: block_size * n_blocks].reshape(n_blocks, block_size, n_strategies)

    half = n_blocks // 2
    logits: list[float] = []
    for train_idx in itertools.combinations(range(n_blocks), half):
        test_idx = [i for i in range(n_blocks) if i not in train_idx]
        train = blocks[list(train_idx)].reshape(-1, n_strategies)
        test = blocks[test_idx].reshape(-1, n_strategies)

        with np.errstate(invalid="ignore", divide="ignore"):
            train_sharpe = train.mean(axis=0) / train.std(axis=0, ddof=1)
        if np.all(np.isnan(train_sharpe)):
            continue  # degenerate split (zero variance everywhere); skip, don't fabricate a pick
        best = int(np.nanargmax(train_sharpe))

        with np.errstate(invalid="ignore", divide="ignore"):
            test_sharpe = test.mean(axis=0) / test.std(axis=0, ddof=1)
        # A NaN OOS Sharpe (zero-variance column) can't be meaningfully ranked
        # on skill either way; treat it as the worst possible OOS outcome
        # rather than silently dropping the split.
        test_sharpe = np.where(np.isnan(test_sharpe), -np.inf, test_sharpe)
        # Relative OOS rank of the IS-best strategy: 1 = worst OOS, N = best OOS.
        rank = int(np.argsort(np.argsort(test_sharpe))[best]) + 1
        omega = rank / (n_strategies + 1)
        omega = min(max(omega, 1e-6), 1 - 1e-6)  # guard logit(0)/logit(1)
        logits.append(math.log(omega / (1 - omega)))

    pbo = float(np.mean([logit <= 0 for logit in logits])) if logits else float("nan")
    return PBOResult(pbo=pbo, n_combinations=len(logits), logits=logits)
