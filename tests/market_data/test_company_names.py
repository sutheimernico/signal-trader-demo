from signal_trader.market_data.company_names import clean_name, load_names


def test_clean_strips_legal_suffixes_and_titlecases():
    assert clean_name("ZIONS BANCORPORATION, NATIONAL ASSOCIATION /UT/") == "Zions Bancorporation"
    assert clean_name("KEYCORP /NEW/") == "Keycorp"
    assert clean_name("COCA COLA CO") == "Coca Cola Co"
    assert clean_name("Alphabet Inc.") == "Alphabet Inc"


def test_load_names_missing_file_returns_empty(tmp_path):
    assert load_names(tmp_path / "nope.json") == {}
