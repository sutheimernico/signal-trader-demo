import numpy as np
import pandas as pd

from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.metrics import compute_metrics
from signal_trader.backtest.tearsheet import build_tearsheet


def _returns(n=300, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(rng.normal(0.0006, 0.01, n), index=idx)


def test_build_tearsheet_writes_a_file(tmp_path):
    r = _returns()
    m = compute_metrics(r)
    out = build_tearsheet(
        returns=r,
        benchmark=None,
        metrics_report=m,
        cost_model=CostModel(0.001, 0.0005),
        title="Test Tearsheet",
        output_path=tmp_path / "report.html",
    )
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_tearsheet_has_no_external_network_references(tmp_path):
    r = _returns()
    m = compute_metrics(r)
    out = build_tearsheet(
        returns=r, benchmark=_returns(seed=4), metrics_report=m,
        cost_model=CostModel(0.001, 0.0005), title="Test",
        output_path=tmp_path / "report.html",
    )
    html = out.read_text(encoding="utf-8")
    assert "http://" not in html
    assert "https://" not in html
    assert "cdn." not in html.lower()


def test_tearsheet_embeds_charts_as_base64_images(tmp_path):
    r = _returns()
    m = compute_metrics(r)
    out = build_tearsheet(
        returns=r, benchmark=None, metrics_report=m,
        cost_model=CostModel(0.001, 0.0005), title="Test",
        output_path=tmp_path / "report.html",
    )
    html = out.read_text(encoding="utf-8")
    assert html.count("data:image/png;base64,") == 3  # equity, drawdown, heatmap


def test_tearsheet_shows_psr_and_dsr_when_present(tmp_path):
    r = _returns()
    m = compute_metrics(r, trial_sharpes=[0.01, 0.02, -0.01])
    assert m.dsr is not None
    out = build_tearsheet(
        returns=r, benchmark=None, metrics_report=m,
        cost_model=CostModel(0.001, 0.0005), title="Test",
        output_path=tmp_path / "report.html",
    )
    html = out.read_text(encoding="utf-8")
    assert f"{m.psr:.3f}" in html
    assert f"{m.dsr:.3f}" in html


def test_tearsheet_shows_dsr_not_available_without_trial_history(tmp_path):
    r = _returns()
    m = compute_metrics(r)
    assert m.dsr is None
    out = build_tearsheet(
        returns=r, benchmark=None, metrics_report=m,
        cost_model=CostModel(0.001, 0.0005), title="Test",
        output_path=tmp_path / "report.html",
    )
    html = out.read_text(encoding="utf-8")
    assert "n/a" in html.lower()


def test_tearsheet_discloses_costs(tmp_path):
    r = _returns()
    m = compute_metrics(r)
    out = build_tearsheet(
        returns=r, benchmark=None, metrics_report=m,
        cost_model=CostModel(commission_per_trade=0.0012, slippage=0.0007),
        title="Test", output_path=tmp_path / "report.html",
    )
    html = out.read_text(encoding="utf-8")
    assert "0.120%" in html  # commission
    assert "0.070%" in html  # slippage


def test_tearsheet_renders_honest_notes():
    r = _returns()
    m = compute_metrics(r)

    def render(notes):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            out = build_tearsheet(
                returns=r, benchmark=None, metrics_report=m,
                cost_model=CostModel(0.001, 0.0005), title="Test",
                output_path=Path(d) / "report.html",
                notes=notes,
            )
            return out.read_text(encoding="utf-8")

    html = render(["ML did not robustly beat the momentum baseline OOS."])
    assert "ML did not robustly beat the momentum baseline OOS." in html
