from pathlib import Path

import signal_trader
from signal_trader import config


def test_package_importable():
    assert signal_trader.__version__ == "0.1.0"


def test_config_paths_are_absolute_and_under_repo():
    assert config.REPO_ROOT.is_dir()
    assert config.DATA_DIR == config.REPO_ROOT / "data"
    assert config.SQLITE_PATH == config.DATA_DIR / "signal_trader.sqlite"
    assert config.PARQUET_DIR == config.DATA_DIR / "bars"
    assert config.SP500_SNAPSHOT == config.REPO_ROOT / "config" / "sp500_snapshot.csv"
    assert isinstance(config.DATA_DIR, Path)


def test_alpaca_keys_default_to_none_when_env_absent(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    creds = config.alpaca_credentials()
    assert creds == (None, None)


def test_alpaca_keys_read_from_env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key123")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret456")
    assert config.alpaca_credentials() == ("key123", "secret456")
