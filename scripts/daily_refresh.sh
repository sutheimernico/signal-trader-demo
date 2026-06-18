#!/usr/bin/env bash
# Daily self-refresh: market-wide insider scan (rolling window) + 13F. Keeps the
# dashboard suggestions fresh with no human action. Logs to /tmp/daily_refresh.log.
set -uo pipefail
cd /home/nicosutheimer/private/signal-trader-demo
END=$(date +%F)
START=$(date -d '21 days ago' +%F)
echo "=== daily_refresh $(date) (insider $START..$END) ==="
uv run python scripts/scan_insider_market.py --start "$START" --end "$END" \
    --min-filings 4 --max-candidates 120 --min-insiders 3 2>&1 | grep -iE "parsed|Persisted" || true
uv run python scripts/ingest_13f.py 2>&1 | grep -iE "Fetched|consensus|Persisted" || true
echo "=== done $(date) ==="
