"""Tests for the run detail page rendering.

Verifies that the run detail page reflects the actual run state (status,
duration, step count) rather than hard-coded placeholders.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def real_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a real data directory backed by the aspara API.

    Writes two runs into the same project:
    - ``wip_run``: a run that has logged 3 steps but has NOT been finished.
    - ``done_run``: a run that has logged 3 steps and been finished.
    """
    data_dir = tmp_path / "aspara-data"
    data_dir.mkdir()
    monkeypatch.setenv("ASPARA_DATA_DIR", str(data_dir))

    # Import lazily so the env var is honored by the aspara config module.
    import aspara

    # WIP run: log 3 steps, do NOT call finish()
    aspara.init(project="proj", name="wip_run", config={"lr": 0.01})
    for i in range(3):
        aspara.log({"loss": 0.5 - i * 0.1}, step=i)
    # Reset module-level run state without finishing the run on disk.
    import aspara.run._api as _api

    _api._current_run = None

    # Finished run: log 3 steps, then finish()
    aspara.init(project="proj", name="done_run", config={"lr": 0.02})
    for i in range(3):
        aspara.log({"loss": 0.6 - i * 0.1}, step=i)
    aspara.finish()

    # Point the dashboard dependencies at this data directory.
    from aspara.dashboard.dependencies import configure_data_dir

    configure_data_dir(str(data_dir))
    try:
        yield data_dir
    finally:
        configure_data_dir(None)


class TestRunDetailRendering:
    """Tests that the run detail HTML reflects actual run state."""

    def test_wip_run_shows_running_status(
        self,
        test_client,
        real_data_dir,
    ) -> None:
        """A WIP run must show 'Running', not 'Completed'."""
        response = test_client.get("/projects/proj/runs/wip_run")
        assert response.status_code == 200
        body = response.text
        assert "Running" in body
        # The previous implementation always showed "Completed"; guard against
        # that regression for WIP runs.
        completed_marker = 'text-status-success font-medium">Completed'
        assert completed_marker not in body

    def test_finished_run_shows_completed_status(
        self,
        test_client,
        real_data_dir,
    ) -> None:
        """A finished run (exit_code 0) must show 'Completed'."""
        response = test_client.get("/projects/proj/runs/done_run")
        assert response.status_code == 200
        assert "Completed" in response.text

    def test_run_detail_shows_duration(self, test_client, real_data_dir) -> None:
        """The run detail page must show a real duration, not the N/A placeholder."""
        import re

        response = test_client.get("/projects/proj/runs/done_run")
        assert response.status_code == 200
        body = response.text
        # The Duration row must not contain the hard-coded "N/A" sentinel.
        match = re.search(r"Duration:</span>\s*<span[^>]*>([^<]+)</span>", body)
        assert match is not None, "Duration row not found in page"
        value = match.group(1).strip()
        assert value != "N/A", f"Duration should not be N/A, got: {value!r}"

    def test_run_detail_shows_step_count(self, test_client, real_data_dir) -> None:
        """The run detail page must show the number of logged steps."""
        response = test_client.get("/projects/proj/runs/done_run")
        assert response.status_code == 200
        body = response.text
        assert "Steps" in body
        # 3 steps were logged.
        assert "3" in body
