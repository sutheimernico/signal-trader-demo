import { useState } from "react";
import { fmtMoney, fmtTime, type PaperTrade } from "../api";

export function PaperTrades({ trades }: { trades: PaperTrade[] }) {
  const [openOnly, setOpenOnly] = useState(false);
  const rows = trades.filter((t) => (openOnly ? t.exit_time === null : true));

  return (
    <section className="view" role="tabpanel">
      <div className="vhead">
        <div>
          <div className="vtitle">Paper trades</div>
          <div className="vnote">
            Trades spawned by accepted suggestions. Paper only — no money moves.
            P&amp;L net of assumed costs.
          </div>
        </div>
        <div className="seg" role="group" aria-label="Filter trades">
          <button data-t="all" aria-pressed={!openOnly} onClick={() => setOpenOnly(false)}>
            All
          </button>
          <button data-t="open" aria-pressed={openOnly} onClick={() => setOpenOnly(true)}>
            Open
          </button>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Ticker</th>
            <th>Side</th>
            <th>Qty</th>
            <th>Entry</th>
            <th>Entry time</th>
            <th>Exit</th>
            <th>Exit time</th>
            <th>P&amp;L net</th>
            <th>From</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={10}>
                <div className="empty">
                  <div className="e1">No paper trades yet</div>
                  <div>The forward run hasn't placed any.</div>
                </div>
              </td>
            </tr>
          ) : (
            rows.map((t, i) => (
              <tr key={t.id} style={{ animationDelay: `${i * 45}ms` }}>
                <td className="mono">{t.id}</td>
                <td>
                  <span className="tk-s">{t.company}</span>
                  <span className="ticker-sub"> {t.ticker}</span>
                </td>
                <td>
                  <span className={`side ${t.side}`}>{t.side}</span>
                </td>
                <td className="mono">{t.qty.toFixed(0)}</td>
                <td className="mono">${t.entry_price.toFixed(2)}</td>
                <td className="mono" style={{ color: "var(--dim)" }}>
                  {fmtTime(t.entry_time)}
                </td>
                <td className="mono">
                  {t.exit_price === null ? (
                    <span className="openl">open</span>
                  ) : (
                    `$${t.exit_price.toFixed(2)}`
                  )}
                </td>
                <td className="mono" style={{ color: "var(--dim)" }}>
                  {t.exit_time === null ? <span className="openl">—</span> : fmtTime(t.exit_time)}
                </td>
                <td>
                  {t.pnl === null ? (
                    <span className="openl">open</span>
                  ) : (
                    <span className={`ret ${t.pnl >= 0 ? "pos" : "neg"}`}>{fmtMoney(t.pnl)}</span>
                  )}
                </td>
                <td>
                  <span className="from">{t.source_suggestion_id}</span>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      <div className="note">
        <b>Plumbing validation — not a performance result.</b> The forward paper
        run only proves the wiring works. A handful of trades over weeks proves
        nothing statistically.
      </div>
    </section>
  );
}
