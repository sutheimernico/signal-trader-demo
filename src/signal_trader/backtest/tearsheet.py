"""Self-built, self-contained HTML tearsheet.

quantstats-reloaded's own `reports.html()` was the natural first choice —
quantstats-reloaded is already a pinned dependency, used elsewhere in
`metrics.py` (via its `stats` module, which works fine). Its `reports`
module does not: `reports.metrics(...)`, in EVERY mode (`basic` and
`full`), raises ``ValueError: Length of values (2) does not match length of
index (1)`` against this repo's pinned pandas — a genuine incompatibility in
the 0.1.0 fork's report renderer, reproduced with plain synthetic data,
independent of anything specific to this repo's inputs. Rather than pin a
different quantstats fork just for the renderer, this module builds the
same content directly: an equity curve, a drawdown chart, a monthly-returns
heatmap, and the honest metric set (CAGR/Sharpe/Sortino/Calmar/MaxDD/
PSR/DSR) plus a cost disclosure — one plain HTML file with the charts
embedded as base64 PNGs (matplotlib, Agg backend). No external CDN, no JS,
no network at generation or view time.

Colors follow this repo's dataviz-skill palette: the equity curve's
benchmark line is muted gray (never a competing hue — it is a reference, not
a series to tell apart), and the monthly heatmap uses the palette's
validated diverging pair, blue (gain) <-> red (loss) with a neutral gray
midpoint. This is a deliberate departure from the usual green/red finance
convention: red-green is a poor pairing for the most common color-vision
deficiency, and blue<->red is the pair this repo's palette actually
validated for CVD separation.
"""
from __future__ import annotations

import base64
import io
from html import escape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: never touch a display, never open a window
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from signal_trader.backtest.costs import CostModel  # noqa: E402
from signal_trader.backtest.metrics import MetricsReport  # noqa: E402

_BLUE = "#2a78d6"  # categorical slot 1 — the strategy series
_RED = "#e34948"  # categorical slot 6 — diverging pole (loss)
_GRAY_MIDPOINT = "#f0efec"  # diverging neutral midpoint ("reads as nothing")
_MUTED_INK = "#898781"  # benchmark reference line, gridlines/axis
_CRITICAL_RED = "#d03b3b"  # status "critical" — drawdown fill
_GRIDLINE = "#e1e0d9"
_PRIMARY_INK = "#0b0b0b"

plt.rcParams["font.family"] = "sans-serif"


def _fig_to_base64_png(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _style_axes(ax: plt.Axes) -> None:
    ax.grid(True, color=_GRIDLINE, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(_MUTED_INK)
    ax.tick_params(colors=_MUTED_INK)
    ax.title.set_color(_PRIMARY_INK)


def _equity_curve_chart(returns: pd.Series, benchmark: pd.Series | None) -> str:
    fig, ax = plt.subplots(figsize=(9, 4))
    (1 + returns).cumprod().plot(ax=ax, label="Strategy", color=_BLUE, linewidth=2)
    if benchmark is not None:
        (1 + benchmark).cumprod().plot(
            ax=ax, label="Buy & Hold", color=_MUTED_INK, linewidth=1.5, linestyle="--"
        )
    ax.set_title("Equity Curve (after costs)")
    ax.set_ylabel("Growth of 1")
    ax.set_xlabel("")
    ax.legend(frameon=False)
    _style_axes(ax)
    return _fig_to_base64_png(fig)


def _drawdown_chart(returns: pd.Series) -> str:
    equity = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.fill_between(drawdown.index, drawdown.to_numpy(), 0, color=_CRITICAL_RED, alpha=0.45)
    ax.plot(drawdown.index, drawdown.to_numpy(), color=_CRITICAL_RED, linewidth=1)
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown")
    ax.set_xlabel("")
    _style_axes(ax)
    return _fig_to_base64_png(fig)


_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _monthly_heatmap(returns: pd.Series) -> str:
    monthly = (1 + returns).resample("ME").prod() - 1.0
    frame = monthly.to_frame("ret")
    frame["year"] = frame.index.year
    frame["month"] = frame.index.month
    pivot = frame.pivot(index="year", columns="month", values="ret").reindex(columns=range(1, 13))

    vmax = max(float(pivot.abs().max().max() or 0.0), 0.01)  # avoid a degenerate 0-width scale
    cmap = LinearSegmentedColormap.from_list("blue_gray_red", [_RED, _GRAY_MIDPOINT, _BLUE])

    fig, ax = plt.subplots(figsize=(9, max(2.0, 0.45 * len(pivot))))
    im = ax.imshow(pivot.to_numpy(dtype=float), cmap=cmap, aspect="auto", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(12))
    ax.set_xticklabels(_MONTH_LABELS)
    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iat[i, j]
            if pd.notna(value):
                ax.text(
                    j, i, f"{value * 100:.1f}", ha="center", va="center",
                    fontsize=7, color=_PRIMARY_INK,
                )
    ax.set_title("Monthly Returns (%) — blue = gain, red = loss")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.colorbar(im, ax=ax, shrink=0.6, label="Monthly return")
    return _fig_to_base64_png(fig)


def _metrics_rows(m: MetricsReport) -> str:
    dsr_cell = (
        f"{m.dsr:.3f}"
        if m.dsr is not None
        else "n/a — run the generating CLI at least twice to build trial history"
    )
    rows = [
        ("CAGR", f"{m.cagr:.2%}"),
        ("Sharpe", f"{m.sharpe:.3f}"),
        ("Sortino", f"{m.sortino:.3f}"),
        ("Calmar", f"{m.calmar:.3f}"),
        ("Max Drawdown", f"{m.max_drawdown:.2%}"),
        ("PSR (probabilistic Sharpe vs 0)", f"{m.psr:.3f}"),
        ("DSR (deflated Sharpe, corrects for trials tried)", dsr_cell),
    ]
    return "".join(f"<tr><th>{escape(k)}</th><td>{escape(v)}</td></tr>" for k, v in rows)


def build_tearsheet(
    *,
    returns: pd.Series,
    benchmark: pd.Series | None,
    metrics_report: MetricsReport,
    cost_model: CostModel,
    title: str,
    output_path: Path,
    notes: list[str] | None = None,
) -> Path:
    """Render a self-contained HTML tearsheet to ``output_path`` and return it.

    ``notes`` are rendered verbatim (already-escaped-safe plain text expected)
    in an "Honest notes" panel — the caller's place to attach the sober,
    non-flattering findings (e.g. the ML-vs-baseline result) so a reader who
    only opens this one file still sees the honest-harness framing, not just
    the flattering numbers of the strategy being reported here.
    """
    equity_img = _equity_curve_chart(returns, benchmark)
    drawdown_img = _drawdown_chart(returns)
    heatmap_img = _monthly_heatmap(returns)
    notes_html = "".join(f"<li>{escape(n)}</li>" for n in (notes or []))

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    max-width: 960px; margin: 32px auto; padding: 0 16px;
    color: {_PRIMARY_INK}; background: #fcfcfb;
  }}
  h1 {{ font-weight: 400; font-size: 1.6rem; }}
  h2 {{ font-weight: 600; font-size: 1.05rem; margin-top: 2rem; color: {_PRIMARY_INK}; }}
  .disclaimer {{
    background: #fff8e6; border: 1px solid #f0d787; padding: 10px 14px;
    border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem;
  }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid {_GRIDLINE}; }}
  th {{ font-weight: 400; color: {_MUTED_INK}; }}
  td {{ font-variant-numeric: tabular-nums; }}
  img {{ max-width: 100%; height: auto; display: block; margin-bottom: 8px; }}
  .honest {{
    background: #f5f5f4; border-left: 4px solid {_CRITICAL_RED};
    padding: 10px 16px; border-radius: 0 6px 6px 0;
  }}
  .honest ul {{ margin: 4px 0; padding-left: 1.2rem; }}
  .caption {{ color: {_MUTED_INK}; font-size: 0.85rem; margin-top: -4px; margin-bottom: 20px; }}
</style>
</head>
<body>
<h1>{escape(title)}</h1>
<p class="disclaimer">Paper-only backtest harness. Not an edge claim, not investment
advice — see the project README's "honest harness" section. All figures below are
AFTER costs.</p>

<h2>Equity Curve</h2>
<img src="data:image/png;base64,{equity_img}" alt="Equity curve: strategy vs buy and hold">

<h2>Drawdown</h2>
<img src="data:image/png;base64,{drawdown_img}" alt="Drawdown over time">

<h2>Monthly Returns</h2>
<img src="data:image/png;base64,{heatmap_img}" alt="Monthly returns heatmap">
<p class="caption">Blue/red instead of the usual green/red: red-green is a poor pairing
for the most common form of color blindness.</p>

<h2>Key Metrics</h2>
<table>{_metrics_rows(metrics_report)}</table>

<h2>Costs (charged, not estimated)</h2>
<table>
<tr><th>Commission per trade</th><td>{cost_model.commission_per_trade:.3%}</td></tr>
<tr><th>Slippage</th><td>{cost_model.slippage:.3%}</td></tr>
</table>

<h2>Honest notes</h2>
<div class="honest"><ul>{notes_html}</ul></div>

</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
