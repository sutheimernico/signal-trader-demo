import pytest

from signal_trader.backtest.breakeven import breakeven_commission


def test_breakeven_found_for_decaying_sharpe():
    # sharpe falls linearly from +2 at cost 0 to -1 at cost 0.02
    def sharpe_at(commission: float) -> float:
        return 2.0 - 150.0 * commission

    be = breakeven_commission(sharpe_at, hi=0.02)
    assert be is not None
    assert abs(sharpe_at(be)) < 1e-3


def test_returns_none_when_sharpe_never_crosses_zero():
    def always_positive(commission: float) -> float:
        return 1.5

    assert breakeven_commission(always_positive, hi=0.02) is None


def test_rejects_nonpositive_starting_sharpe():
    def negative(commission: float) -> float:
        return -0.5

    with pytest.raises(ValueError):
        breakeven_commission(negative, hi=0.02)
