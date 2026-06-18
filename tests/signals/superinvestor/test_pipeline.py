import datetime as dt

import pandas as pd

from signal_trader.signals.superinvestor.pipeline import build_13f_signals
from signal_trader.sources.superinvestor_13f import HoldingObservation
from signal_trader.store.signal_store import SignalStore


class FakeSource:
    def __init__(self, obs):
        self._obs = obs
    def fetch_new_long_positions(self, fund_names):
        return [o for o in self._obs if o.fund in fund_names]


def _obs(fund, ticker, known_day=3):
    return HoldingObservation(
        fund=fund, ticker=ticker, issuer=ticker, value=1e6, shares=1000.0,
        put_call="", timestamp_event=dt.date(2024, 6, 30),
        timestamp_known=dt.date(2024, 8, known_day),
        url=f"https://sec.gov/{fund}", accession_no=f"{fund}-1",
    )


def _close_lookup():
    idx = pd.date_range("2024-06-01", periods=120, freq="B")
    return {"NVDA": pd.Series(range(100, 220), index=idx, dtype=float),
            "AAPL": pd.Series(range(100, 220), index=idx, dtype=float)}


def test_consensus_two_funds_same_ticker_is_one_stronger_signal(tmp_path):
    src = FakeSource([_obs("Burry", "NVDA", 3), _obs("Tepper", "NVDA", 5),
                      _obs("Burry", "AAPL", 3)])
    store = SignalStore(tmp_path / "t.sqlite")
    n = build_13f_signals(src, ["Burry", "Tepper"], close_lookup=_close_lookup(), store=store)
    rows = {r.ticker: r for r in store.read_signals(source="superinvestor_13f")}
    assert n == 2
    assert rows["NVDA"].confidence > rows["AAPL"].confidence  # 2 funds > 1 fund
    import json
    p = json.loads(rows["NVDA"].raw_payload_json)
    assert set(p["owners"]) == {"Burry", "Tepper"}
    assert rows["NVDA"].timestamp_known == dt.date(2024, 8, 5)  # latest filing
    assert rows["NVDA"].price_at_known is not None
