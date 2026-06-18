import datetime as dt

import pandas as pd

from signal_trader.signals.congress.pipeline import persist_congress_signals
from signal_trader.sources.congress_trades import CongressObservation
from signal_trader.store.signal_store import SignalStore


def _o(member, ticker, td="2026-05-15", kd="2026-06-01"):
    return CongressObservation(
        member=member, ticker=ticker,
        transaction_date=dt.date.fromisoformat(td),
        timestamp_known=dt.date.fromisoformat(kd),
        amount="", url=f"http://h/{member}", doc_id=member,
    )


def _close():
    idx = pd.date_range("2026-04-01", periods=80, freq="B")
    return {"HD": pd.Series(range(100, 180), index=idx, dtype=float)}


def test_consensus_distinct_members_dedup(tmp_path):
    store = SignalStore(tmp_path / "t.sqlite")
    obs = [_o("Alice", "HD"), _o("Alice", "HD"),  # dup -> counted once
           _o("Bob", "HD"), _o("Carol", "AAPL")]
    n = persist_congress_signals(obs, _close(), store)
    rows = {r.ticker: r for r in store.read_signals(source="congress_house")}
    assert n == 2
    import json
    hd = json.loads(rows["HD"].raw_payload_json)
    assert hd["n_insiders"] == 2  # Alice + Bob (dup dropped)
    assert rows["HD"].price_at_known is not None
