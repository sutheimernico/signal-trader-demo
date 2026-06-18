import datetime as dt

from signal_trader.signals.insider.opportunistic import keep_opportunistic
from signal_trader.sources.insider_source import InsiderObservation


def _obs(owner, ticker, year, month, day=10):
    return InsiderObservation(
        ticker=ticker, reporting_owner=owner, role="Director",
        transaction_code="P", acquired_disposed="A", shares=100.0, price=10.0,
        timestamp_event=dt.date(year, month, day),
        timestamp_known=dt.date(year, month, day + 2),
        is_10b5_1=False, accession_no=f"{owner}-{year}-{month}",
    )


def test_drops_three_year_same_month_routine_trader():
    # Same owner+ticker, January in 2021, 2022, 2023 -> routine -> all dropped
    hist = [_obs("Jane", "AAPL", y, 1) for y in (2021, 2022, 2023)]
    assert keep_opportunistic(hist) == []


def test_keeps_irregular_trader():
    hist = [_obs("Bob", "AAPL", 2021, 3), _obs("Bob", "AAPL", 2022, 7)]
    assert len(keep_opportunistic(hist)) == 2


def test_routine_classification_is_per_owner_ticker_not_global():
    routine = [_obs("Jane", "AAPL", y, 1) for y in (2021, 2022, 2023)]
    one_off = [_obs("Jane", "MSFT", 2023, 1)]
    kept = keep_opportunistic(routine + one_off)
    assert kept == one_off


def test_only_drops_the_routine_month_not_other_months():
    routine_jan = [_obs("Jane", "AAPL", y, 1) for y in (2021, 2022, 2023)]
    other = [_obs("Jane", "AAPL", 2023, 6)]
    kept = keep_opportunistic(routine_jan + other)
    assert kept == other


# Fix 1: short-window degradation warning
def test_short_window_emits_warning(caplog):
    """< 3-year span (< 1095 days) triggers a WARNING about unreliable routine classification."""
    import logging
    obs = [_obs("Bob", "AAPL", 2024, 1), _obs("Bob", "AAPL", 2024, 6)]
    with caplog.at_level(logging.WARNING, logger="signal_trader.signals.insider.opportunistic"):
        keep_opportunistic(obs)
    assert any("routine" in r.message.lower() for r in caplog.records)


def test_long_window_no_short_window_warning(caplog):
    """>= 3-year span does NOT trigger the short-window WARNING."""
    import logging
    # Span: 2021-01-10 to 2024-01-10 = 3 years > 1095 days
    obs = [_obs("Bob", "AAPL", 2021, 1), _obs("Bob", "AAPL", 2024, 1)]
    with caplog.at_level(logging.WARNING, logger="signal_trader.signals.insider.opportunistic"):
        keep_opportunistic(obs)
    assert not any("routine" in r.message.lower() for r in caplog.records)
