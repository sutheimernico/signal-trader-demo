import { useCallback, useEffect, useState } from "react";
import {
  fetchPaperTrades,
  fetchSourceScores,
  fetchSuggestions,
  type PaperTrade,
  type SourceScore,
  type Suggestion,
} from "./api";
import { Suggestions } from "./components/Suggestions";
import { Scorecard } from "./components/Scorecard";
import { PaperTrades } from "./components/PaperTrades";

type Tab = "suggestions" | "scores" | "trades";

const TABS: { id: Tab; label: string }[] = [
  { id: "suggestions", label: "Suggestions" },
  { id: "scores", label: "Scorecard" },
  { id: "trades", label: "Paper" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("suggestions");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [scores, setScores] = useState<SourceScore[]>([]);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSuggestions = useCallback(async () => {
    setSuggestions(await fetchSuggestions("all"));
  }, []);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const [sug, sc, tr] = await Promise.all([
          fetchSuggestions("all"),
          fetchSourceScores(),
          fetchPaperTrades(),
        ]);
        if (!live) return;
        setSuggestions(sug);
        setScores(sc);
        setTrades(tr);
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const counts = {
    suggestions: suggestions.filter((s) => s.status === "open").length,
    scores: scores.length,
    trades: trades.filter((t) => t.exit_time === null).length,
  };

  return (
    <div id="app" className="in">
      <div className="wrap">
        <header className="top">
          <div className="mark">
            K<span className="hi">I</span>T
          </div>
          <div className="sub">signal harness</div>
          <div className="spacer" />
          <div className="pit">point in time · paper only</div>
        </header>

        <div className="banner">
          <span className="tag">no alpha</span>
          <span>
            <b>Plumbing validation — not a performance result.</b>{" "}
            <span className="t">
              The board never says you're winning. Numbers are after assumed
              costs, shown against buy-and-hold.
            </span>
          </span>
        </div>

        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              className="tab"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
            >
              {t.label} <span className="n">{counts[t.id]}</span>
            </button>
          ))}
        </nav>

        <main>
          {error && <div className="err">API error: {error}. Is the backend running on :8000?</div>}
          {loading ? (
            <div className="loading">Loading…</div>
          ) : (
            <>
              {tab === "suggestions" && (
                <Suggestions suggestions={suggestions} onDecided={loadSuggestions} />
              )}
              {tab === "scores" && <Scorecard scores={scores} />}
              {tab === "trades" && <PaperTrades trades={trades} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
