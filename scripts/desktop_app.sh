#!/usr/bin/env bash
# One-click launcher for the Signal Harness dashboard (paper-only, real data).
#
# Serves the FastAPI backend AND the built React frontend from one process on
# one port, then opens the Windows default browser. Builds the frontend on
# first run (or when missing). Real SEC/Alpaca data flows through the CLIs;
# only the trading money is paper. Stop with Ctrl-C.
set -euo pipefail

PORT="${PORT:-8000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) Build the frontend if there is no production bundle yet.
if [ ! -f "frontend/dist/index.html" ]; then
  echo "[desktop] building dashboard (first run)…"
  ( cd frontend && npm install --no-audit --no-fund && npm run build )
fi

URL="http://localhost:${PORT}"

# 2) Open the Windows browser once the server answers (background waiter).
open_browser() {
  for _ in $(seq 1 40); do
    if curl -fsS "${URL}/source-scores" >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
  # WSL → Windows default browser. Fall back to wslview/xdg-open if present.
  if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$URL" || true
  elif command -v wslview     >/dev/null 2>&1; then wslview "$URL" || true
  elif command -v xdg-open    >/dev/null 2>&1; then xdg-open "$URL" || true
  fi
}
open_browser &

# 3) Serve API + dashboard (foreground; Ctrl-C stops it).
echo "[desktop] Signal Harness on ${URL}  (Ctrl-C to stop)"
exec uv run python scripts/run_api.py --host 127.0.0.1 --port "$PORT"
