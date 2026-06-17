"""Foundation report: run the baseline through BOTH engines, compare to the
after-cost buy-and-hold benchmark, and quantify the headline artifact —
'vectorized looks better than event-driven on identical signals' (Spec §5).

Every number is after costs; every engine is shown with the full honest
metric set (never Sharpe alone).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from signal_trader.backtest.benchmark import buy_and_hold_equity
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.engine.backtesting_py import BacktestingPyAdapter
from signal_trader.backtest.engine.vectorbt_engine import VectorbtAdapter
from signal_trader.backtest.metrics import MetricsReport, compute_metrics


def _ohlcv_from_close(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": close.shift(1).fillna(close.iloc[0]),
            "High": close * 1.001,
            "Low": close * 0.999,
            "Close": close,
            "Volume": 1_000_000.0,
        }
    )


@dataclass
class FoundationReport:
    engine_metrics: dict[str, MetricsReport]
    benchmark_metrics: MetricsReport
    vectorized_minus_event_driven_sharpe: float

    def render(self) -> str:
        lines = ["=== Foundation Report (all figures after costs) ===", ""]
        for engine, m in self.engine_metrics.items():
            lines.append(
                f"[{engine}] CAGR={m.cagr:.3f} Sharpe={m.sharpe:.3f} "
                f"Sortino={m.sortino:.3f} Calmar={m.calmar:.3f} "
                f"MaxDD={m.max_drawdown:.3f} PSR={m.psr:.3f}"
            )
        b = self.benchmark_metrics
        lines.append(
            f"[Buy & Hold (after costs)] CAGR={b.cagr:.3f} Sharpe={b.sharpe:.3f} "
            f"Sortino={b.sortino:.3f} Calmar={b.calmar:.3f} "
            f"MaxDD={b.max_drawdown:.3f} PSR={b.psr:.3f}"
        )
        lines.append("")
        lines.append(
            "Artifact — vectorbt Sharpe minus backtesting.py Sharpe: "
            f"{self.vectorized_minus_event_driven_sharpe:+.3f} "
            "(positive = vectorized looks better than event-driven on the "
            "same signals; the realism gap, not an edge)."
        )
        return "\n".join(lines)


def build_foundation_report(
    close: pd.Series, cost_model: CostModel, lookback: int = 50
) -> FoundationReport:
    event = BacktestingPyAdapter(cost_model).run(
        _ohlcv_from_close(close), lookback=lookback
    )
    vector = VectorbtAdapter(cost_model).run(close, lookback=lookback)
    bench_equity = buy_and_hold_equity(close, cost_model)

    engine_metrics = {
        event.engine: compute_metrics(event.returns()),
        vector.engine: compute_metrics(vector.returns()),
    }
    benchmark_metrics = compute_metrics(bench_equity.pct_change().dropna())
    gap = engine_metrics["vectorbt"].sharpe - engine_metrics["backtesting.py"].sharpe
    return FoundationReport(
        engine_metrics=engine_metrics,
        benchmark_metrics=benchmark_metrics,
        vectorized_minus_event_driven_sharpe=gap,
    )
