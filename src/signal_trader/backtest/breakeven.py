"""Break-even-cost check: at what per-trade commission does Sharpe hit 0?

A strategy that only works at unrealistically low costs is fragile. We
bisect on commission, assuming Sharpe is non-increasing in cost (true for a
trading strategy). Returns None if Sharpe stays positive across the range.
"""
from __future__ import annotations

from collections.abc import Callable


def breakeven_commission(
    sharpe_at: Callable[[float], float],
    lo: float = 0.0,
    hi: float = 0.05,
    tol: float = 1e-4,
    max_iter: int = 60,
) -> float | None:
    """Smallest commission at which `sharpe_at(commission)` == 0.

    Raises if Sharpe is already <= 0 at `lo` (nothing to break even from).
    """
    s_lo = sharpe_at(lo)
    if s_lo <= 0:
        raise ValueError("Sharpe must be positive at lo to find a break-even")
    if sharpe_at(hi) > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        s_mid = sharpe_at(mid)
        if abs(s_mid) < tol:
            return mid
        if s_mid > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
