import datetime as dt

from signal_trader.signals.insider.filters import keep_open_market_purchases
from signal_trader.sources.insider_source import InsiderObservation


def _obs(code="P", acq="A", plan=False, **over):
    base = dict(
        ticker="AAPL", reporting_owner="X", role="Director",
        transaction_code=code, acquired_disposed=acq, shares=100.0, price=10.0,
        timestamp_event=dt.date(2024, 1, 10), timestamp_known=dt.date(2024, 1, 12),
        is_10b5_1=plan, accession_no="a",
    )
    base.update(over)
    return InsiderObservation(**base)


def test_keeps_plain_open_market_purchase():
    assert keep_open_market_purchases([_obs()]) == [_obs()]


def test_drops_sales_and_non_p_codes():
    kept = keep_open_market_purchases([_obs(code="S"), _obs(code="M"), _obs(code="A")])
    assert kept == []


def test_drops_acquisitions_that_are_not_acquired_flag():
    assert keep_open_market_purchases([_obs(code="P", acq="D")]) == []


def test_drops_10b5_1_plan_trades():
    assert keep_open_market_purchases([_obs(plan=True)]) == []


def test_keeps_only_qualifying_rows_from_mixed_batch():
    kept = keep_open_market_purchases(
        [_obs(), _obs(code="S"), _obs(plan=True), _obs(code="P", acq="A", shares=5.0)]
    )
    assert len(kept) == 2
