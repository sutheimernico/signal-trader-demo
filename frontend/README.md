# Signal Harness — Dashboard (React 19 + Vite + TS)

The "KIT" scoreboard dashboard for the measurement harness. Three views —
Suggestions, Source Scorecard, Paper Trades — talking to the FastAPI backend.
Sober by design: it never frames anything as edge; it surfaces data lag and thin
samples. Ported from the design kit `../signal-trader_v7_kit.html`.

## Run

```bash
# 1) start the backend (serves the data the dashboard reads)
cd ..
uv run python scripts/run_api.py --port 8000

# 2) start the dashboard
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The API base URL is the single constant `API_BASE` in `src/api.ts`. CORS for the
Vite dev origin is enabled in the backend (`src/signal_trader/api/app.py`).

## Verify

```bash
npm run build        # tsc (strict) + vite production build
npm run test         # vitest: formatting helpers + Suggestions decide flow
```
