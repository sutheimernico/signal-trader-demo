"""Read-mostly FastAPI app exposing the harness state to the dashboard.

Serves Suggestions, per-source hit-rates (with data-lag always visible, Spec
§8.4), and PaperTrades from the existing SQLite stores. The only write is the
user DECISION on a suggestion (Spec §8.8: the system proposes, the user
decides). No performance is framed as edge — these are raw measurement surfaces
(Spec §3). Built via create_app(db_path) so tests run against a temp DB.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from signal_trader import config
from signal_trader.market_data.company_names import load_names
from signal_trader.store.paper_trade_store import PaperTradeStore
from signal_trader.store.signal_store import SignalStore
from signal_trader.store.suggestion_store import SuggestionStore

# Local dashboard dev servers (Vite). This API is local single-user and
# paper-only; CORS is opened to the dev origins so the React app can fetch it.
_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


class DecisionBody(BaseModel):
    decision: Literal["accepted", "rejected"]


def create_app(db_path: Path, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Signal Trader — measurement harness (paper-only)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    suggestions = SuggestionStore(db_path)
    signals = SignalStore(db_path)
    trades = PaperTradeStore(db_path)
    names = load_names(config.DATA_DIR / "ticker_names.json")  # ticker -> company

    @app.get("/suggestions")
    def get_suggestions(status: str | None = None) -> list[dict]:
        return [
            {
                "ticker": s.ticker,
                "company": names.get(s.ticker.upper(), s.ticker),
                "consolidated_score": s.consolidated_score,
                "contributing_signals": json.loads(s.contributing_signals_json),
                "created_at": s.created_at.isoformat(),
                "latest_known": s.latest_known.isoformat(),
                "horizon": s.horizon,
                "status": s.status,
                "user_decision": s.user_decision,
                "decided_at": s.decided_at.isoformat() if s.decided_at else None,
            }
            for s in suggestions.read_suggestions(status=status)
        ]

    @app.get("/source-scores")
    def get_source_scores() -> list[dict]:
        return [
            {
                "source": sc.source,
                "window": sc.window,
                "n_signals": sc.n_signals,
                "hit_rate": sc.hit_rate,
                "avg_forward_return": sc.avg_forward_return,
                "avg_data_lag_days": sc.avg_data_lag_days,
            }
            for sc in signals.read_source_scores()
        ]

    @app.get("/paper-trades")
    def get_paper_trades(open_only: bool = False) -> list[dict]:
        return [
            {
                "id": t.id,
                "ticker": t.ticker,
                "company": names.get(t.ticker.upper(), t.ticker),
                "side": t.side,
                "qty": t.qty,
                "entry_price": t.entry_price,
                "entry_time": t.entry_time.isoformat(),
                "exit_price": t.exit_price,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "pnl": t.pnl,
                "source_suggestion_id": t.source_suggestion_id,
            }
            for t in trades.read_trades(open_only=open_only)
        ]

    @app.post("/suggestions/{ticker}/{created_at}/decision")
    def post_decision(ticker: str, created_at: str, body: DecisionBody) -> dict:
        try:
            parsed = dt.date.fromisoformat(created_at)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"created_at not an ISO date: {created_at!r}"
            ) from exc
        try:
            suggestions.record_decision(
                ticker=ticker,
                created_at=parsed,
                decision=body.decision,
                decided_at=dt.date.today(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ticker": ticker, "created_at": created_at, "status": body.decision}

    # Serve the built React dashboard from the same origin (one process, one
    # port) when a production build exists. Mounted last so API routes win.
    # Absent in tests/dev (Vite serves the UI then) — guarded by existence.
    frontend = static_dir if static_dir is not None else config.REPO_ROOT / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")

    return app
