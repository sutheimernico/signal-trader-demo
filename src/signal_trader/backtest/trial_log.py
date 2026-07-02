"""Append-only log of backtest/ML-experiment trials.

Systematic trial-count tracking for the Deflated Sharpe Ratio (Bailey &
Lopez de Prado 2014): DSR needs to know how many configurations were tried
and how dispersed their Sharpe ratios were. Guessing that number by hand (the
earlier ``evaluate_ml(..., n_configs_tested=...)`` knob) is exactly the kind
of unverifiable claim the honest-harness framing rejects — nothing ever
actually populated it, so the CLI always printed "1 configuration(s) tested"
regardless of how many times it had really been run. Every CLI run that
reports a Sharpe now appends one record here; `metrics.deflated_sharpe_ratio`
reads the trial history for the SAME ``family`` (a comparable strategy
search) back to compute an honest correction.

Local, offline, plain JSON Lines under ``data/`` (gitignored like the rest of
the cache — the log rebuilds itself as CLIs are re-run; deleting it just
resets the trial count to 0, it does not affect PIT integrity of anything
else). No server, no schema migration; corrupt or foreign-family lines are
skipped defensively rather than raised.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrialRecord:
    family: str  # comparable strategy-search bucket, e.g. "foundation_backtest"
    label: str  # human-readable config description, for audit ("AAPL lookback=50")
    sharpe: float  # per-period (non-annualized) Sharpe — see metrics.per_period_sharpe
    n_obs: int  # sample length behind the Sharpe
    logged_at: str  # ISO-8601 UTC timestamp


def log_trial(path: Path, family: str, label: str, sharpe: float, n_obs: int) -> TrialRecord:
    """Append one trial record to ``path``, creating parent dirs as needed."""
    record = TrialRecord(
        family=family,
        label=label,
        sharpe=sharpe,
        n_obs=n_obs,
        logged_at=dt.datetime.now(tz=dt.UTC).isoformat(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record)) + "\n")
    return record


def load_trial_sharpes(path: Path, family: str) -> list[float]:
    """Return every previously logged per-period Sharpe for ``family``, oldest
    first.

    Missing file -> ``[]`` (first-ever trial for this family, no history
    yet). Malformed JSON lines or lines from a different family are skipped
    rather than raised — a corrupt log line must never crash a report.
    """
    if not path.exists():
        return []
    sharpes: list[float] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("family") == family and "sharpe" in record:
                sharpes.append(float(record["sharpe"]))
    return sharpes
