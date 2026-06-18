import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from signal_trader.paper.alpaca.broker_adapter import AlpacaPaperBroker
from signal_trader.paper.broker import Broker, Fill


def _order(order_id="o1", symbol="AAPL", qty=10.0, filled_avg_price=151.0,
           filled_at="2024-01-16T15:00:00Z"):
    o = MagicMock()
    o.id = order_id
    o.symbol = symbol
    o.qty = qty
    o.filled_avg_price = filled_avg_price
    o.filled_at = filled_at
    return o


def _patched(submit_return, get_returns):
    client = MagicMock()
    client.submit_order.return_value = submit_return
    client.get_order_by_id.side_effect = get_returns
    return client


def test_conforms_to_broker_protocol():
    with patch("signal_trader.paper.alpaca.broker_adapter.TradingClient",
               return_value=MagicMock()):
        broker = AlpacaPaperBroker(api_key="k", secret_key="s", sleep=lambda s: None)
    assert isinstance(broker, Broker)


def test_buy_returns_fill_from_actual_filled_order():
    filled = _order(filled_avg_price=151.0)
    client = _patched(_order(filled_avg_price=None), [filled])
    with patch("signal_trader.paper.alpaca.broker_adapter.TradingClient",
               return_value=client) as ctor:
        broker = AlpacaPaperBroker(api_key="k", secret_key="s", sleep=lambda s: None)
        fill = broker.submit_market_buy("AAPL", qty=10.0)

    ctor.assert_called_once_with("k", "s", paper=True)
    assert isinstance(fill, Fill)
    assert fill.side == "buy"
    assert fill.price == 151.0
    assert fill.qty == 10.0
    assert fill.filled_at == dt.datetime(2024, 1, 16, 15, 0, tzinfo=dt.UTC)


def test_sell_returns_fill():
    filled = _order(filled_avg_price=160.0, symbol="AAPL")
    client = _patched(filled, [filled])
    with patch("signal_trader.paper.alpaca.broker_adapter.TradingClient",
               return_value=client):
        broker = AlpacaPaperBroker(api_key="k", secret_key="s", sleep=lambda s: None)
        fill = broker.submit_market_sell("AAPL", qty=5.0)
    assert fill.side == "sell"
    assert fill.price == 160.0


def test_unfilled_order_raises_no_fabricated_price():
    never = [_order(filled_avg_price=None) for _ in range(10)]
    client = _patched(_order(filled_avg_price=None), never)
    with patch("signal_trader.paper.alpaca.broker_adapter.TradingClient",
               return_value=client):
        broker = AlpacaPaperBroker(api_key="k", secret_key="s",
                                   sleep=lambda s: None, max_poll_attempts=3)
        with pytest.raises(ValueError):
            broker.submit_market_buy("AAPL", qty=1.0)


def test_missing_credentials_raise_before_network():
    with pytest.raises(ValueError):
        AlpacaPaperBroker(api_key=None, secret_key=None)
