@echo off
REM Autonomous ML paper-trade cycle (real prices, DEMO money) — runs in WSL.
REM Scheduled weekdays shortly after US market open. Logs to /tmp/ml_paper.log.
wsl.exe -e bash -lc "cd /home/nicosutheimer/private/signal-trader-demo && uv run python scripts/paper_trade_ml.py >> /tmp/ml_paper.log 2>&1"
