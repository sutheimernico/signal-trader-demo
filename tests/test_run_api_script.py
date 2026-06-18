import sys
from unittest.mock import patch

import scripts.run_api as run_api


def test_main_builds_app_and_serves_without_blocking(tmp_path, monkeypatch):
    monkeypatch.setattr(run_api.config, "SQLITE_PATH", tmp_path / "t.sqlite")
    with patch.object(run_api, "uvicorn") as uv, patch.object(
        sys, "argv", ["run_api.py", "--port", "9001"]
    ):
        run_api.main()
    # the app is built and handed to uvicorn.run on the requested port
    assert uv.run.call_args.kwargs["port"] == 9001
