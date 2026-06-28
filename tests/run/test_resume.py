"""Tests for resuming an existing run with aspara.init(resume=True)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import aspara


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point aspara at a temporary data directory."""
    data_dir = tmp_path / "aspara-data"
    data_dir.mkdir()
    monkeypatch.setenv("ASPARA_DATA_DIR", str(data_dir))
    return data_dir


def _read_metadata(data_dir: Path, project: str, run: str) -> dict:
    p = data_dir / project / f"{run}.meta.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _read_metrics_steps(data_dir: Path, project: str, run: str) -> list[int]:
    p = data_dir / project / f"{run}.jsonl"
    if not p.exists():
        return []
    steps: list[int] = []
    for line in p.read_text().splitlines():
        if line.strip():
            steps.append(json.loads(line)["step"])
    return steps


class TestLocalResume:
    """resume=True should continue an existing local run."""

    def test_resume_reuses_run_id(self, isolated_data_dir: Path) -> None:
        aspara.init(project="p", name="r")
        first_id = aspara._get_current_run().id
        aspara.finish(quiet=True)

        aspara.init(project="p", name="r", resume=True)
        second_id = aspara._get_current_run().id
        aspara.finish(quiet=True)

        assert second_id == first_id, "resume must reuse the existing run_id"

    def test_resume_continues_step_numbering(self, isolated_data_dir: Path) -> None:
        aspara.init(project="p", name="r")
        aspara.log({"loss": 0.5}, step=0)
        aspara.log({"loss": 0.4}, step=1)
        aspara.finish(quiet=True)

        aspara.init(project="p", name="r", resume=True)
        aspara.log({"loss": 0.3}, step=2)
        aspara.finish(quiet=True)

        steps = _read_metrics_steps(isolated_data_dir, "p", "r")
        assert steps == [0, 1, 2]

    def test_resume_resets_finish_state(self, isolated_data_dir: Path) -> None:
        aspara.init(project="p", name="r")
        aspara.finish(quiet=True)
        meta_before = _read_metadata(isolated_data_dir, "p", "r")
        assert meta_before["is_finished"] is True

        aspara.init(project="p", name="r", resume=True)
        meta_after = _read_metadata(isolated_data_dir, "p", "r")
        assert meta_after["is_finished"] is False
        assert meta_after["status"] == "wip"
        aspara.finish(quiet=True)

    def test_resume_without_existing_run_creates_new(self, isolated_data_dir: Path) -> None:
        """resume=True when no existing run should just create a new run."""
        aspara.init(project="p", name="r", resume=True)
        run = aspara._get_current_run()
        assert run is not None
        assert run.id is not None
        aspara.finish(quiet=True)

    def test_resume_preserves_start_time(self, isolated_data_dir: Path) -> None:
        aspara.init(project="p", name="r")
        aspara.finish(quiet=True)
        meta_before = _read_metadata(isolated_data_dir, "p", "r")
        start_before = meta_before["start_time"]

        aspara.init(project="p", name="r", resume=True)
        aspara.finish(quiet=True)
        meta_after = _read_metadata(isolated_data_dir, "p", "r")
        assert meta_after["start_time"] == start_before
