"""Forward paper loop: accepted Suggestions -> opened PaperTrades.

PLUMBING VALIDATION, not a performance result (Spec §3, §8.10). For each
accepted suggestion that has no paper trade yet, submit a paper market buy and
record the trade from the ACTUAL fill (price/time the broker reports, never an
idealized number — Spec §8.1). Idempotent via source_suggestion_id, so re-running
the loop never double-opens. Point-in-time safe by construction: a trade can only
follow a human acceptance, which itself happens after the suggestion's known date.
"""
from __future__ import annotations

import datetime as dt
import logging

from signal_trader.paper.broker import Broker
from signal_trader.store.paper_trade_store import PaperTradeRecord, PaperTradeStore
from signal_trader.store.suggestion_store import SuggestionStore

_LOG = logging.getLogger(__name__)


def _suggestion_id(ticker: str, created_at: dt.date) -> str:
    return f"{ticker}|{created_at.isoformat()}"


def open_accepted_suggestions(
    suggestion_store: SuggestionStore,
    trade_store: PaperTradeStore,
    broker: Broker,
    qty: float = 1.0,
) -> int:
    """Open a paper trade for each accepted suggestion not yet traded. Returns count."""
    already_traded = {
        t.source_suggestion_id for t in trade_store.read_trades()
    }
    opened = 0
    for sug in suggestion_store.read_suggestions(status="accepted"):
        sid = _suggestion_id(sug.ticker, sug.created_at)
        if sid in already_traded:
            continue
        # One bad symbol/rejection must not abort the remaining suggestions:
        # log and skip, never silently drop the rest (Spec honesty principle).
        try:
            fill = broker.submit_market_buy(sug.ticker, qty)
            trade_store.insert_trade(PaperTradeRecord(
                ticker=sug.ticker,
                side="buy",
                qty=fill.qty,
                entry_price=fill.price,
                entry_time=fill.filled_at,
                exit_price=None,
                exit_time=None,
                pnl=None,
                source_suggestion_id=sid,
            ))
        except Exception as exc:  # noqa: BLE001 - log + skip, continue the loop
            _LOG.warning("skip paper-open for %s: %s", sid, exc)
            continue
        already_traded.add(sid)
        opened += 1
    return opened


def close_due_trades(
    trade_store: PaperTradeStore,
    broker: Broker,
    as_of: dt.datetime,
    hold_days: int,
) -> int:
    """Close open trades held >= hold_days as of `as_of`. Returns count closed.

    Exit price/time/pnl come from the ACTUAL sell fill the broker reports
    (Spec §8.1) — never an idealized close. `as_of` is the wall-clock the loop
    runs at (injected so tests are deterministic); a trade is due when at least
    `hold_days` have elapsed since its entry. One failed sell logs and skips,
    never aborting the rest.
    """
    closed = 0
    hold = dt.timedelta(days=hold_days)
    for trade in trade_store.read_trades(open_only=True):
        if as_of - trade.entry_time < hold:
            continue
        try:
            fill = broker.submit_market_sell(trade.ticker, trade.qty)
            pnl = (fill.price - trade.entry_price) * trade.qty
            trade_store.close_trade(
                trade.id, exit_price=fill.price,
                exit_time=fill.filled_at, pnl=pnl,
            )
        except Exception as exc:  # noqa: BLE001 - log + skip, continue the loop
            _LOG.warning("skip paper-close for trade %s: %s", trade.id, exc)
            continue
        closed += 1
    return closed
