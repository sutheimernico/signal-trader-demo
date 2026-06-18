import datetime as dt

from signal_trader.signals.insider.cluster import (
    cluster_purchases,
    keep_small_cap,
)
from signal_trader.sources.insider_source import InsiderObservation


def _obs(owner, ticker, known_day, price=10.0, shares=100.0):
    return InsiderObservation(
        ticker=ticker, reporting_owner=owner, role="Director",
        transaction_code="P", acquired_disposed="A", shares=shares, price=price,
        timestamp_event=dt.date(2024, 1, known_day),
        timestamp_known=dt.date(2024, 1, known_day),
        is_10b5_1=False, accession_no=f"{owner}-{known_day}",
    )


def test_cluster_requires_min_distinct_insiders_in_window():
    obs = [_obs("A", "AAPL", 1), _obs("B", "AAPL", 3), _obs("C", "AAPL", 5)]
    clusters = cluster_purchases(obs, window_days=10, min_insiders=3)
    assert len(clusters) == 1
    assert clusters[0].ticker == "AAPL"
    assert clusters[0].n_insiders == 3


def test_no_cluster_when_window_too_narrow():
    obs = [_obs("A", "AAPL", 1), _obs("B", "AAPL", 3), _obs("C", "AAPL", 20)]
    assert cluster_purchases(obs, window_days=5, min_insiders=3) == []


def test_same_insider_counted_once():
    obs = [_obs("A", "AAPL", 1), _obs("A", "AAPL", 2), _obs("A", "AAPL", 3)]
    assert cluster_purchases(obs, window_days=10, min_insiders=3) == []


def test_cluster_known_date_is_latest_filing_in_window():
    obs = [_obs("A", "AAPL", 1), _obs("B", "AAPL", 4), _obs("C", "AAPL", 6)]
    clusters = cluster_purchases(obs, window_days=10, min_insiders=3)
    assert clusters[0].timestamp_known == dt.date(2024, 1, 6)


def test_small_cap_tilt_filters_by_price_proxy_threshold():
    cheap = _obs("A", "PENNY", 1, price=3.0)
    pricey = _obs("B", "MEGA", 1, price=400.0)
    kept = keep_small_cap([cheap, pricey], max_price=50.0)
    assert kept == [cheap]


# Fix 3: emit ALL non-overlapping clusters, not just the first one
def test_two_independent_clusters_both_emitted():
    """Two buying waves separated by more than window_days must both produce clusters."""
    # Wave 1: days 1-5 (known dates 1-5 in January 2024)
    wave1 = [_obs("A", "AAPL", 1), _obs("B", "AAPL", 3), _obs("C", "AAPL", 5)]
    # Wave 2: days 30-34 (>10 days after wave 1 ends -> non-overlapping)
    wave2 = [
        InsiderObservation(
            ticker="AAPL", reporting_owner=owner, role="Director",
            transaction_code="P", acquired_disposed="A", shares=100.0, price=10.0,
            timestamp_event=dt.date(2024, 2, day),
            timestamp_known=dt.date(2024, 2, day),
            is_10b5_1=False, accession_no=f"{owner}-feb-{day}",
        )
        for owner, day in [("D", 1), ("E", 3), ("F", 5)]
    ]
    clusters = cluster_purchases(wave1 + wave2, window_days=10, min_insiders=3)
    assert len(clusters) == 2, f"expected 2 clusters, got {len(clusters)}"
    known_dates = {c.timestamp_known for c in clusters}
    assert dt.date(2024, 1, 5) in known_dates
    assert dt.date(2024, 2, 5) in known_dates
