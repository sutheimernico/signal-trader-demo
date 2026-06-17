import datetime as dt

import pytest

from signal_trader.sources.insider_source import InsiderObservation, InsiderSource


def _obs(**over):
    base = dict(
        ticker="AAPL",
        reporting_owner="Jane Doe",
        role="Director",
        transaction_code="P",
        acquired_disposed="A",
        shares=1000.0,
        price=150.0,
        timestamp_event=dt.date(2024, 1, 10),
        timestamp_known=dt.date(2024, 1, 12),
        is_10b5_1=False,
        accession_no="0000000000-24-000001",
    )
    base.update(over)
    return InsiderObservation(**base)


def test_observation_is_frozen_and_holds_fields():
    obs = _obs()
    assert obs.ticker == "AAPL"
    assert obs.transaction_code == "P"
    assert obs.timestamp_known == dt.date(2024, 1, 12)
    with pytest.raises(AttributeError):  # FrozenInstanceError is an AttributeError subclass
        obs.ticker = "MSFT"  # frozen


def test_known_must_not_predate_event():
    with pytest.raises(ValueError):
        _obs(timestamp_event=dt.date(2024, 1, 12), timestamp_known=dt.date(2024, 1, 10))


def test_notional_is_shares_times_price():
    assert _obs(shares=10.0, price=5.0).notional == 50.0


def test_protocol_is_runtime_checkable():
    class Dummy:
        def fetch(self, tickers, start, end):
            return []
    assert isinstance(Dummy(), InsiderSource)
