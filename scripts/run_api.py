"""CLI: serve the dashboard backend API (read-mostly, local, paper-only).

    uv run python scripts/run_api.py --port 8000

Builds the FastAPI app over the project SQLite store and serves it with uvicorn.
The dashboard (Track C) talks to this. No live broker/SEC contact here — it only
reads what the ingest and forward-loop CLIs have already persisted.
"""
from __future__ import annotations

import argparse

import uvicorn

from signal_trader import config
from signal_trader.api.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the dashboard API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(config.SQLITE_PATH), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
