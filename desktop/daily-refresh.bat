@echo off
REM Daily self-refresh of insider + 13F suggestions (runs in WSL).
wsl.exe -e bash -lc "./scripts/daily_refresh.sh >> /tmp/daily_refresh.log 2>&1"
