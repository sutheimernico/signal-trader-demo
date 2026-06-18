# Signal-Trader Dashboard — Design Brief

> Hand this file to a design tool (e.g. Claude Artifacts) to generate the dashboard UI. It is self-contained: product framing, the user, exact data shapes with sample payloads, the views to build, and the non-negotiable honesty constraints. Build a single-page React 19 + TypeScript app (Vite). Talk to the FastAPI backend described below. **No backend code needed in the design — mock the JSON payloads given here.**

---

## 1. What this product is (and is NOT)

A **local, paper-only, honest measurement harness** for a long-term stock-suggestion system. It ingests public insider-trading filings (SEC Form 4), turns clustered insider purchases into *suggestions*, and tracks how those suggestions would have performed — **after costs, against a benchmark**.

**The cardinal rule — honesty over hype.** This is an engineering/learning artifact, never an edge claim. The UI must:
- **Never** frame any number as "alpha", "edge", "profit opportunity", or a buy recommendation. Suggestions are *proposals the user evaluates*, not signals to act on.
- **Always** show the **data lag** of each source (insiders file 2–3 days after they trade; the pre-filing move is already gone — the system only sees the residual).
- **Always** show performance **after costs** and **against a benchmark** (buy-and-hold after the same costs). Never a Sharpe number alone.
- Label the live paper-trading run explicitly as **"Plumbing validation — not a performance result."**

The tone is a **sober analyst's instrument panel**, not a trading app. Think Bloomberg-terminal-meets-lab-notebook, not Robinhood. Calm, dense, factual. No green up-arrows celebrating gains, no gamification, no confetti.

## 2. The user

A single, technical user (the developer) running this locally. They:
- Review **open suggestions**, inspect the contributing signals and the source's track record, then **accept or reject** each (the system only proposes — the human decides).
- Watch **per-source hit-rates and data-lag** to judge whether a source is worth trusting.
- Monitor **paper trades** (open + closed) that resulted from accepted suggestions.

No login, no multi-user, no settings page needed for v1.

## 3. Visual direction

- **Layout:** left nav or top tabs → three primary views (Suggestions, Source Scorecard, Paper Trades). A persistent thin header banner stating the honesty framing.
- **Palette:** neutral/dark analyst theme. Use color *functionally* (e.g. status chips), not emotionally. Avoid red=bad/green=good for returns — returns are facts, not verdicts. A muted diverging scale is fine for magnitude.
- **Typography:** monospace or tabular figures for all numbers so columns align. Clear numeric precision (e.g. hit-rate 0.66, returns as %, lag in days).
- **Density:** tables-first. Cards for individual suggestions are OK, but the data must read like a spreadsheet you trust.
- **Empty states:** explicit ("No open suggestions" / "No paper trades yet — the forward run hasn't placed any"). Never blank.

## 4. Views to build

### View A — Suggestions (default)
A table or card list of suggestions. Each row/card shows:
- `ticker`, `consolidated_score` (sum of contributing signal confidences — show as a magnitude bar, NOT a star rating), `horizon` (long/short).
- `created_at` and `latest_known` — and a **prominent "data known as of"** treatment, because point-in-time honesty is the whole point.
- `contributing_signals` — expandable detail: source + number of contributing insiders.
- `status` chip: **open / accepted / rejected**.
- For `open` rows: **Accept** and **Reject** buttons → POST decision.
- For decided rows: show `user_decision` + `decided_at`, controls disabled.
- Filter control by status (open / accepted / rejected / all).

### View B — Source Scorecard
A table, one row per (source, window). Columns:
- `source`, `window` (e.g. "5d").
- `n_signals`, `hit_rate` (0–1, render as % with the raw count beside it so a 0.66 over 3 signals doesn't look authoritative — **small-n must look small-n**).
- `avg_forward_return` (%), `avg_data_lag_days` — **the lag column must be visually unmissable**, ideally with a one-line caption: "filing delay — the move before this is already gone."

### View C — Paper Trades
A table of paper trades (open + closed), filterable to open-only. Columns:
- `id`, `ticker`, `side`, `qty`, `entry_price`, `entry_time`.
- `exit_price`, `exit_time`, `pnl` (null while open → render "open" not "0").
- `source_suggestion_id` (which suggestion spawned it).
- A persistent caption on this view: **"Forward paper run = plumbing validation, not a performance result. A handful of trades over weeks proves nothing statistically."**

## 5. Backend API (FastAPI, runs at http://localhost:8000)

All read endpoints return JSON arrays. One write endpoint records the user's decision. Mock these exact shapes in the design.

### `GET /suggestions?status=open`
`status` optional: `open` | `accepted` | `rejected`; omit for all.
```json
[
  {
    "ticker": "AAPL",
    "consolidated_score": 1.0,
    "contributing_signals": { "source": "insider_form4", "n_contributing": 2 },
    "created_at": "2024-01-12",
    "latest_known": "2024-01-12",
    "horizon": "long",
    "status": "open",
    "user_decision": null,
    "decided_at": null
  }
]
```

### `GET /source-scores`
```json
[
  {
    "source": "insider_form4",
    "window": "5d",
    "n_signals": 3,
    "hit_rate": 0.66,
    "avg_forward_return": 0.012,
    "avg_data_lag_days": 2.0
  }
]
```

### `GET /paper-trades?open_only=true`
`open_only` optional boolean.
```json
[
  {
    "id": 1,
    "ticker": "AAPL",
    "side": "buy",
    "qty": 10.0,
    "entry_price": 150.0,
    "entry_time": "2024-01-15T14:30:00",
    "exit_price": null,
    "exit_time": null,
    "pnl": null,
    "source_suggestion_id": "AAPL|2024-01-12"
  }
]
```

### `POST /suggestions/{ticker}/{created_at}/decision`
`created_at` is the ISO date from the suggestion. Body:
```json
{ "decision": "accepted" }
```
`decision` ∈ `{"accepted", "rejected"}`. Returns `200` with `{ "ticker", "created_at", "status" }`. `404` if the suggestion doesn't exist, `422` on a malformed date or invalid decision value.

## 6. Tech constraints for the generated app

- **React 19 + TypeScript, Vite.** Function components + hooks only.
- Data fetching: keep it simple — `fetch` in an effect, or TanStack Query if you want caching (single small dataset, so plain fetch is fine). Show loading and error states.
- After a successful decision POST, refetch `/suggestions` (optimistic update optional).
- Make the API base URL a single constant (`http://localhost:8000`) so it's easy to change.
- Accessibility: the accept/reject controls must be real buttons; tables need headers; don't encode meaning in color alone (pair color with text/icon).

## 7. One-paragraph summary to paste as the prompt

> Build a React 19 + TypeScript (Vite) single-page dashboard for a local, paper-only stock-suggestion *measurement harness*. It is a sober analyst's instrument panel — honest, dense, tabular, never hyped; suggestions are proposals the user accepts or rejects, never buy calls. Three views: (A) Suggestions — table with status chips and accept/reject buttons, point-in-time "known as of" dates prominent; (B) Source Scorecard — per-source hit-rate with n shown so small samples look small, and an unmissable data-lag column; (C) Paper Trades — open/closed trades with a standing caption that the forward run is plumbing validation, not a performance result. Always show performance after costs and the data lag of each source; never frame anything as edge/alpha. Use the JSON shapes and the FastAPI endpoints in this brief; mock the data. Show loading/error/empty states.
