from unittest.mock import MagicMock, patch

import pytest

from signal_trader.paper.alpaca.paper_stub import AlpacaPaperStub


def test_submit_market_buy_builds_paper_request_and_returns_id():
    fake_client = MagicMock()
    fake_client.submit_order.return_value = MagicMock(id="order-123")
    with patch(
        "signal_trader.paper.alpaca.paper_stub.TradingClient",
        return_value=fake_client,
    ) as ctor:
        stub = AlpacaPaperStub(api_key="k", secret_key="s")
        order_id = stub.submit_market_buy("AAPL", qty=1)

    ctor.assert_called_once_with("k", "s", paper=True)
    assert order_id == "order-123"
    _, kwargs = fake_client.submit_order.call_args
    req = kwargs["order_data"]
    assert req.symbol == "AAPL"
    assert req.qty == 1


def test_missing_credentials_raise_before_any_network_call():
    with pytest.raises(ValueError):
        AlpacaPaperStub(api_key=None, secret_key=None)
