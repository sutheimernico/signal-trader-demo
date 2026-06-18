// API client + types for the Signal Harness dashboard.
// Mirrors the FastAPI read API (src/signal_trader/api/app.py). Single local
// user, paper-only. Base URL is the one constant to change for a non-default port.

// In dev (Vite on :5173) talk to the backend on :8000 (CORS-allowed). In the
// production build the API is served from the SAME origin by uvicorn, so a
// relative base ("") just works on whatever host/port the app is launched on.
export const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

export type Status = "open" | "accepted" | "rejected";
export type Decision = "accepted" | "rejected";

export interface Suggestion {
  ticker: string;
  consolidated_score: number;
  contributing_signals: {
    source: string;
    n_contributing: number;
    sources?: string[]; // EDGAR filing links (source of record)
  };
  created_at: string;
  latest_known: string;
  horizon: string;
  status: Status;
  user_decision: Decision | null;
  decided_at: string | null;
}

export interface SourceScore {
  source: string;
  window: string;
  n_signals: number;
  hit_rate: number;
  avg_forward_return: number;
  avg_data_lag_days: number;
}

export interface PaperTrade {
  id: number;
  ticker: string;
  side: string;
  qty: number;
  entry_price: number;
  entry_time: string;
  exit_price: number | null;
  exit_time: string | null;
  pnl: number | null;
  source_suggestion_id: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) throw new Error(`GET ${path} failed: ${resp.status}`);
  return resp.json() as Promise<T>;
}

export const fetchSuggestions = (status?: Status | "all") =>
  getJSON<Suggestion[]>(
    status && status !== "all" ? `/suggestions?status=${status}` : "/suggestions",
  );

export const fetchSourceScores = () => getJSON<SourceScore[]>("/source-scores");

export const fetchPaperTrades = (openOnly = false) =>
  getJSON<PaperTrade[]>(`/paper-trades${openOnly ? "?open_only=true" : ""}`);

export async function postDecision(
  ticker: string,
  createdAt: string,
  decision: Decision,
): Promise<void> {
  const resp = await fetch(
    `${API_BASE}/suggestions/${encodeURIComponent(ticker)}/${createdAt}/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    },
  );
  if (!resp.ok) throw new Error(`decision failed: ${resp.status}`);
}

// ---- formatting helpers (ported from the design kit) ----

/** Whole days between an ISO date and `now` (end-of-day anchored), never negative. */
export function daysSince(iso: string, now: Date = new Date()): number {
  const then = new Date(`${iso}T16:00:00`).getTime();
  return Math.max(0, Math.round((now.getTime() - then) / 86_400_000));
}

/** Signed percent with a real minus sign; magnitude only, no color verdict. */
export function fmtPct(x: number): string {
  return (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(1) + "%";
}

/** Signed money with a real minus sign. A gain and a loss read the same. */
export function fmtMoney(x: number): string {
  return (x >= 0 ? "+" : "−") + "$" + Math.abs(x).toFixed(2);
}

/** ISO datetime -> "YYYY-MM-DD HH:MM". */
export function fmtTime(iso: string): string {
  return iso.replace("T", " ").slice(0, 16);
}
