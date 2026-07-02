from signal_trader.backtest.trial_log import load_trial_sharpes, log_trial


def test_log_trial_creates_parent_dir_and_is_readable_back(tmp_path):
    path = tmp_path / "nested" / "trial_log.jsonl"
    log_trial(path, family="foo", label="cfg-1", sharpe=0.05, n_obs=100)
    assert path.exists()
    assert load_trial_sharpes(path, family="foo") == [0.05]


def test_log_trial_appends_preserving_order(tmp_path):
    path = tmp_path / "trial_log.jsonl"
    log_trial(path, family="foo", label="cfg-1", sharpe=0.01, n_obs=10)
    log_trial(path, family="foo", label="cfg-2", sharpe=0.02, n_obs=20)
    log_trial(path, family="foo", label="cfg-3", sharpe=0.03, n_obs=30)
    assert load_trial_sharpes(path, family="foo") == [0.01, 0.02, 0.03]


def test_load_trial_sharpes_filters_by_family(tmp_path):
    path = tmp_path / "trial_log.jsonl"
    log_trial(path, family="foo", label="a", sharpe=0.01, n_obs=10)
    log_trial(path, family="bar", label="b", sharpe=0.99, n_obs=10)
    log_trial(path, family="foo", label="c", sharpe=0.02, n_obs=10)
    assert load_trial_sharpes(path, family="foo") == [0.01, 0.02]
    assert load_trial_sharpes(path, family="bar") == [0.99]


def test_load_trial_sharpes_empty_when_file_missing(tmp_path):
    assert load_trial_sharpes(tmp_path / "does_not_exist.jsonl", family="foo") == []


def test_load_trial_sharpes_skips_malformed_lines(tmp_path):
    path = tmp_path / "trial_log.jsonl"
    log_trial(path, family="foo", label="a", sharpe=0.01, n_obs=10)
    with path.open("a", encoding="utf-8") as f:
        f.write("not json at all\n")
        f.write("\n")  # blank line
    log_trial(path, family="foo", label="b", sharpe=0.02, n_obs=10)
    assert load_trial_sharpes(path, family="foo") == [0.01, 0.02]


def test_log_trial_record_carries_label_and_n_obs(tmp_path):
    path = tmp_path / "trial_log.jsonl"
    record = log_trial(path, family="foo", label="AAPL lookback=50", sharpe=0.1, n_obs=250)
    assert record.family == "foo"
    assert record.label == "AAPL lookback=50"
    assert record.n_obs == 250
    assert record.logged_at  # non-empty ISO timestamp
