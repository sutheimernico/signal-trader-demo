import datetime as dt

from signal_trader.signals.consolidate.consolidate import consolidate_per_ticker
from signal_trader.store.signal_store import StoredSignal


def _sig(ticker, known, conf):
    return StoredSignal(
        ticker=ticker, source="insider_form4", signal_type="insider_cluster_purchase",
        direction="long", timestamp_event=dt.date(2024, 1, 1),
        timestamp_known=known, price_at_known=100.0,
        raw_payload_json="{}", confidence=conf,
    )


def test_consolidated_score_sums_contributing_confidence():
    sigs = [_sig("AAPL", dt.date(2024, 1, 2), 0.4), _sig("AAPL", dt.date(2024, 1, 5), 0.6)]
    out = consolidate_per_ticker(sigs)
    assert out["AAPL"].consolidated_score == 1.0
    assert out["AAPL"].n_contributing == 2
    assert out["AAPL"].latest_known == dt.date(2024, 1, 5)


def test_separate_tickers_kept_apart():
    out = consolidate_per_ticker([_sig("AAPL", dt.date(2024, 1, 2), 0.4),
                                  _sig("MSFT", dt.date(2024, 1, 2), 0.7)])
    assert set(out) == {"AAPL", "MSFT"}
