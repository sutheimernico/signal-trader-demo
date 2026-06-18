import { fmtPct, type SourceScore } from "../api";

const MAX_LAG = 50;

export function Scorecard({ scores }: { scores: SourceScore[] }) {
  return (
    <section className="view" role="tabpanel">
      <div className="vhead">
        <div>
          <div className="vtitle">Source scorecard</div>
          <div className="vnote">
            Hit-rate per source and window, with sample size <b>n</b> next to
            every rate so a thin sample reads as thin. Read the orange lag column
            first.
          </div>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Window</th>
            <th>n</th>
            <th>Hit-rate</th>
            <th>Avg fwd. ret.</th>
            <th className="lag">Data lag</th>
          </tr>
        </thead>
        <tbody>
          {scores.map((r, i) => {
            const small = r.n_signals < 5;
            const lw = Math.min(100, (r.avg_data_lag_days / MAX_LAG) * 100);
            return (
              <tr key={`${r.source}-${r.window}`} style={{ animationDelay: `${i * 45}ms` }}>
                <td>
                  <span className="src-s">{r.source}</span>
                </td>
                <td className="mono">{r.window}</td>
                <td className={`mono ${small ? "smalln" : ""}`} style={{ fontWeight: 700 }}>
                  {r.n_signals}
                </td>
                <td>
                  <span className={`nbox ${small ? "smalln" : ""}`}>
                    <span className="hr">{r.hit_rate.toFixed(2)}</span>
                    <span className="nn">n={r.n_signals}</span>
                    {small && <span className="thin">thin</span>}
                  </span>
                </td>
                <td>
                  <span className={`ret ${r.avg_forward_return >= 0 ? "pos" : "neg"}`}>
                    {fmtPct(r.avg_forward_return)}
                  </span>
                </td>
                <td className="lag">
                  <span className="lagcell">
                    <span className="lagbar">
                      <i style={{ width: `${lw}%` }} />
                    </span>
                    <span className="lagnum">{r.avg_data_lag_days.toFixed(0)}d</span>
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="lagcap">
        <b>Filing delay — the move before this is already gone.</b> Insiders ~2–3
        days; Congress up to ~45; 13F holdings ~45 days after quarter-end. The
        harness only ever sees the residual.
      </div>
    </section>
  );
}
