"""Tests for user-facing console output of aspara.init()/finish()."""

from __future__ import annotations

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


class TestInitOutput:
    """init() should print actionable guidance for first-time users."""

    def test_init_mentions_project_name(
        self,
        isolated_data_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        aspara.init(project="myproj", name="run1")
        aspara.finish(quiet=True)
        out = capsys.readouterr().out
        assert "myproj" in out

    def test_init_mentions_data_directory(
        self,
        isolated_data_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        aspara.init(project="myproj", name="run1")
        aspara.finish(quiet=True)
        out = capsys.readouterr().out
        # The data directory path should appear so users know where data lands.
        assert str(isolated_data_dir) in out

    def test_init_mentions_dashboard_command(
        self,
        isolated_data_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """init() should hint at how to view results in the dashboard."""
        aspara.init(project="myproj", name="run1")
        aspara.finish(quiet=True)
        out = capsys.readouterr().out
        assert "aspara dashboard" in out or "aspara serve" in out


class TestFinishOutput:
    """finish() should also guide users to the dashboard."""

    def test_finish_mentions_dashboard_command(
        self,
        isolated_data_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        aspara.init(project="myproj", name="run1")
        aspara.log({"loss": 0.5})
        aspara.finish()
        out = capsys.readouterr().out
        assert "aspara dashboard" in out or "aspara serve" in out

    def test_quiet_finish_suppresses_dashboard_hint(
        self,
        isolated_data_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """quiet=True must suppress user-facing output (context manager path)."""
        aspara.init(project="myproj", name="run1")
        # Clear init output so we only capture finish() output below.
        capsys.readouterr()
        aspara.finish(quiet=True)
        out = capsys.readouterr().out
        # quiet=True is used by the context manager exit and by init() when it
        # auto-finishes a previous run; it should not print the dashboard hint.
        assert "aspara dashboard" not in out
        assert "aspara serve" not in out
