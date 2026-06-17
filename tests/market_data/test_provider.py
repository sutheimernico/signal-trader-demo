from unittest.mock import patch

import pandas as pd
import pytest

from signal_trader.market_data.provider import PriceProvider, YFinanceProvider


def _fake_yf_multiindex(tickers):
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    frames = {}
    for i, t in enumerate(tickers):
        base = 100 + i
        frames[(t, "Open")] = [base, base + 1, base + 2]
        frames[(t, "High")] = [base + 1, base + 2, base + 3]
        frames[(t, "Low")] = [base - 1, base, base + 1]
        frames[(t, "Close")] = [base + 0.5, base + 1.5, base + 2.5]
        frames[(t, "Volume")] = [1e6, 1.1e6, 1.2e6]
    cols = pd.MultiIndex.from_tuples(frames.keys(), names=["Ticker", "Price"])
    return pd.DataFrame(frames, index=idx).reindex(columns=cols)


def test_yfinance_provider_satisfies_protocol():
    assert isinstance(YFinanceProvider(), PriceProvider)


def test_fetch_returns_long_frame_with_expected_columns():
    with patch("signal_trader.market_data.provider.yf.download") as dl:
        dl.return_value = _fake_yf_multiindex(["AAPL", "MSFT"])
        out = YFinanceProvider().fetch(["AAPL", "MSFT"], "2020-01-01", "2020-01-06")
    assert list(out.columns) == [
        "ticker", "date", "open", "high", "low", "close", "volume"
    ]
    assert set(out["ticker"]) == {"AAPL", "MSFT"}
    assert len(out) == 6
    assert pd.api.types.is_datetime64_any_dtype(out["date"])


def test_fetch_passes_auto_adjust_true_and_group_by_ticker():
    with patch("signal_trader.market_data.provider.yf.download") as dl:
        dl.return_value = _fake_yf_multiindex(["AAPL"])
        YFinanceProvider().fetch(["AAPL"], "2020-01-01", "2020-01-06")
    _, kwargs = dl.call_args
    assert kwargs["auto_adjust"] is True
    assert kwargs["group_by"] == "ticker"
    assert kwargs["progress"] is False


def test_fetch_empty_tickers_raises():
    with pytest.raises(ValueError):
        YFinanceProvider().fetch([], "2020-01-01", "2020-01-06")
