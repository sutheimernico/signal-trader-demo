from signal_trader.market_data import universe


def test_load_universe_returns_sorted_unique_tickers():
    tickers = universe.load_sp500_tickers()
    assert len(tickers) >= 50
    assert tickers == sorted(set(tickers))
    assert all(t.isupper() and t.strip() == t for t in tickers)


def test_load_universe_normalizes_dotted_tickers():
    # Yahoo uses '-' where the index uses '.', e.g. BRK.B -> BRK-B
    tickers = universe.load_sp500_tickers()
    assert "BRK-B" in tickers or "BRK.B" not in tickers


def test_docstring_documents_survivorship_caveat():
    assert "survivorship" in universe.load_sp500_tickers.__doc__.lower()


def test_subset_limits_count():
    assert len(universe.load_sp500_tickers(limit=10)) == 10
