"""Autonomous ML paper loop (Phase 4, Track 2).

Fully automated, NO human confirmation (paper money only — separate from the
human-facing insider track). Given a forecaster already fit on history, score
today's point-in-time features, go long the top-k predicted names, and open paper
trades from the ACTUAL broker fills. Idempotent per (ticker, date) via the
PaperTrade store's UNIQUE source id; one bad order logs and skips, never aborts.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from signal_trader.paper.broker import Broker
from signal_trader.store.paper_trade_store import PaperTradeRecord, PaperTradeStore
from signal_trader.strategy.shortterm.model import Forecaster

_LOG = logging.getLogger(__name__)


def open_ml_positions(
    latest_X: pd.DataFrame,
    forecaster: Forecaster,
    trade_store: PaperTradeStore,
    broker: Broker,
    top_k: int = 3,
    qty: float = 1.0,
) -> int:
    """Open paper trades for the top-k predicted names. Returns count opened."""
    if latest_X.empty:
        return 0
    preds = np.asarray(forecaster.predict(latest_X), dtype=float)
    order = np.argsort(preds)[::-1][:top_k]
    already = {t.source_suggestion_id for t in trade_store.read_trades()}
    opened = 0
    for pos in order:
        ticker, date = latest_X.index[pos]
        sid = f"ML|{ticker}|{pd.Timestamp(date).date().isoformat()}"
        if sid in already:
            continue
        try:
            fill = broker.submit_market_buy(ticker, qty)
            trade_store.insert_trade(PaperTradeRecord(
                ticker=ticker, side="buy", qty=fill.qty,
                entry_price=fill.price, entry_time=fill.filled_at,
                exit_price=None, exit_time=None, pnl=None,
                source_suggestion_id=sid,
            ))
        except Exception as exc:  # noqa: BLE001 - log + skip, continue
            _LOG.warning("skip ML paper-open for %s: %s", sid, exc)
            continue
        already.add(sid)
        opened += 1
    return opened
