import pytest

from signal_trader.backtest.costs import CostModel


def test_commission_fraction_default():
    cm = CostModel(commission_per_trade=0.001, slippage=0.0005)
    assert cm.commission_per_trade == 0.001
    assert cm.slippage == 0.0005


def test_round_trip_fraction_is_two_legs_of_commission_plus_slippage():
    cm = CostModel(commission_per_trade=0.001, slippage=0.0005)
    # entry + exit: 2 * (commission + slippage)
    assert cm.round_trip_fraction() == pytest.approx(2 * (0.001 + 0.0005))


def test_apply_slippage_buy_raises_price_sell_lowers_price():
    cm = CostModel(commission_per_trade=0.0, slippage=0.01)
    assert cm.fill_price(100.0, side="buy") == pytest.approx(101.0)
    assert cm.fill_price(100.0, side="sell") == pytest.approx(99.0)


def test_negative_costs_rejected():
    with pytest.raises(ValueError):
        CostModel(commission_per_trade=-0.001, slippage=0.0)
    with pytest.raises(ValueError):
        CostModel(commission_per_trade=0.0, slippage=-0.1)


def test_invalid_side_rejected():
    cm = CostModel(commission_per_trade=0.0, slippage=0.01)
    with pytest.raises(ValueError):
        cm.fill_price(100.0, side="hold")
