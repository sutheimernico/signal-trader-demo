import { useState } from "react";
import {
  daysSince,
  postDecision,
  type Decision,
  type Status,
  type Suggestion,
} from "../api";

type Filter = Status | "all";

const FILTERS: { f: Filter; label: string }[] = [
  { f: "open", label: "Open" },
  { f: "accepted", label: "Acc" },
  { f: "rejected", label: "Rej" },
  { f: "all", label: "All" },
];

export function Suggestions({
  suggestions,
  onDecided,
}: {
  suggestions: Suggestion[];
  onDecided: () => void | Promise<void>;
}) {
  const [filter, setFilter] = useState<Filter>("open");
  const [busy, setBusy] = useState<string | null>(null);

  const rows = suggestions.filter((s) => (filter === "all" ? true : s.status === filter));

  async function decide(s: Suggestion, decision: Decision) {
    const key = `${s.ticker}|${s.created_at}`;
    setBusy(key);
    try {
      await postDecision(s.ticker, s.created_at, decision);
      await onDecided();
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="view" role="tabpanel">
      <div className="vhead">
        <div>
          <div className="vtitle">Suggestions</div>
          <div className="vnote">
            Clustered insider buys turned into proposals — never calls. The
            scoreboard's left cell is how <b>stale</b> the data already was when
            you saw it. An orange kit-number means it's still your call. The
            system only proposes.
          </div>
        </div>
        <div className="seg" role="group" aria-label="Filter by status">
          {FILTERS.map((x) => (
            <button
              key={x.f}
              data-f={x.f}
              aria-pressed={filter === x.f}
              onClick={() => setFilter(x.f)}
            >
              {x.label}
            </button>
          ))}
        </div>
      </div>

      <div className="cards">
        {rows.length === 0 ? (
          <div className="empty">
            <div className="e1">No {filter} suggestions</div>
            <div>Nothing matches this filter right now.</div>
          </div>
        ) : (
          rows.map((s, i) => {
            const stale = daysSince(s.latest_known);
            const w = Math.min(100, (s.consolidated_score / 2) * 100);
            const decided = s.status !== "open";
            const no = String(i + 1).padStart(2, "0");
            const key = `${s.ticker}|${s.created_at}`;
            return (
              <div
                key={key}
                className={`card ${decided ? "decided" : "open"}`}
                style={{ animationDelay: `${i * 55}ms` }}
              >
                <div className="card-top">
                  <div className="kitno">{no}</div>
                  <div className="ct-main">
                    <div>
                      <div className="company">{s.company}</div>
                      <div className="ticker-sub">{s.ticker} · {s.horizon}-term</div>
                    </div>
                    <div className={`chip ${s.status}`}>{s.status}</div>
                  </div>
                </div>
                <div className="board">
                  <div className="cell stale">
                    <div className="lab">data age when seen</div>
                    <div className="big">T+{stale}d</div>
                    <div className="ax">already stale</div>
                  </div>
                  <div className="cell">
                    <div className="lab">score</div>
                    <div className="big">{s.consolidated_score.toFixed(1)}</div>
                    <div className="score-line">
                      <span className="track">
                        <i style={{ width: `${w}%` }} />
                      </span>
                    </div>
                  </div>
                </div>
                <div className="meta">
                  {(() => {
                    const is13f = s.contributing_signals.source.includes("13f");
                    const label = is13f
                      ? "superinvestor 13F"
                      : s.contributing_signals.source;
                    const noun = is13f ? "famous funds" : "insiders";
                    const lag = is13f
                      ? "13F is filed ~45 days after quarter end — a known lag, not pre-news."
                      : "Insiders file 2–3 days after they trade — the pre-filing move is gone; this is the residual only.";
                    const count =
                      s.contributing_signals.n_insiders ??
                      s.contributing_signals.n_contributing;
                    return (
                      <>
                        <span className="src">{label}</span> · {count} {noun} bought
                        (consensus). {lag}
                      </>
                    );
                  })()}
                  {s.contributing_signals.insiders &&
                    s.contributing_signals.insiders.length > 0 && (
                      <span className="insiders">
                        Who: {s.contributing_signals.insiders.join(" · ")}
                      </span>
                    )}
                  {s.contributing_signals.sources &&
                    s.contributing_signals.sources.length > 0 && (
                      <span className="sources">
                        SEC source:{" "}
                        {s.contributing_signals.sources.map((u, j) => (
                          <a
                            key={u}
                            href={u}
                            target="_blank"
                            rel="noreferrer noopener"
                          >
                            filing {j + 1}
                          </a>
                        ))}
                      </span>
                    )}
                </div>
                <div className="card-foot">
                  <div className="asof">
                    created {s.created_at} · known {s.latest_known}
                  </div>
                  {decided ? (
                    <div className="decided-l">
                      decision <b>{s.user_decision}</b> · {s.decided_at}
                    </div>
                  ) : (
                    <div className="act">
                      <button
                        className="b acc"
                        disabled={busy === key}
                        onClick={() => decide(s, "accepted")}
                      >
                        Accept
                      </button>
                      <button
                        className="b rej"
                        disabled={busy === key}
                        onClick={() => decide(s, "rejected")}
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
