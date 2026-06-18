@echo off
REM ============================================================
REM  Signal Harness — one-click launcher (Windows -> WSL)
REM  Double-click to start the dashboard. It builds on first run,
REM  serves API + UI on one port, and opens your browser.
REM  Close this window (or Ctrl-C) to stop the app.
REM ============================================================
title Signal Harness
wsl.exe -e bash -lc "cd /home/nicosutheimer/private/signal-trader-demo && ./scripts/desktop_app.sh"
echo.
echo Signal Harness stopped. You can close this window.
pause
