"""Unit tests for CLI helper functions in aspara.cli."""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from aspara.cli import _get_version, find_available_port, get_default_port, main, parse_serve_components


class TestParseServeComponents:
    """Tests for parse_serve_components()."""

    def test_empty_list_defaults_to_dashboard_only(self) -> None:
        assert parse_serve_components([]) == (True, False)

    def test_together_enables_both(self) -> None:
        assert parse_serve_components(["together"]) == (True, True)

    def test_dashboard_only(self) -> None:
        assert parse_serve_components(["dashboard"]) == (True, False)

    def test_tracker_only(self) -> None:
        assert parse_serve_components(["tracker"]) == (False, True)

    def test_dashboard_and_tracker(self) -> None:
        assert parse_serve_components(["dashboard", "tracker"]) == (True, True)

    def test_case_insensitive(self) -> None:
        assert parse_serve_components(["Dashboard", "Tracker"]) == (True, True)

    def test_together_case_insensitive(self) -> None:
        assert parse_serve_components(["TOGETHER"]) == (True, True)

    def test_invalid_component_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid component"):
            parse_serve_components(["invalid"])

    def test_invalid_component_message_lists_valid_options(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            parse_serve_components(["foo"])
        msg = str(exc_info.value)
        assert "dashboard" in msg
        assert "tracker" in msg
        assert "together" in msg

    def test_together_overrides_explicit_components(self) -> None:
        """'together' should enable both even if only 'together' is given."""
        assert parse_serve_components(["together"]) == (True, True)

    def test_together_with_other_components(self) -> None:
        """'together' takes precedence regardless of other components."""
        assert parse_serve_components(["tracker", "together"]) == (True, True)


class TestGetDefaultPort:
    """Tests for get_default_port()."""

    def test_dashboard_only_returns_3141(self) -> None:
        assert get_default_port(True, False) == 3141

    def test_tracker_only_returns_3142(self) -> None:
        assert get_default_port(False, True) == 3142

    def test_both_returns_3141(self) -> None:
        assert get_default_port(True, True) == 3141

    def test_neither_returns_3141(self) -> None:
        assert get_default_port(False, False) == 3141


class TestFindAvailablePort:
    """Tests for find_available_port()."""

    def test_returns_port_when_available(self) -> None:
        """Should return start_port if it's not in use."""
        # Use a high port that's very likely free
        port = find_available_port(start_port=54321, max_attempts=5)
        assert port is not None
        assert 54321 <= port < 54326

    def test_returns_none_when_all_in_use(self) -> None:
        """Should return None when all ports in range are in use."""
        # Create sockets to occupy ports
        sockets: list[socket.socket] = []
        try:
            for i in range(5):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", 54330 + i))
                s.listen(1)
                sockets.append(s)

            result = find_available_port(start_port=54330, max_attempts=5)
            assert result is None
        finally:
            for s in sockets:
                s.close()

    def test_skips_occupied_port(self) -> None:
        """Should skip an occupied port and find the next available one."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 54340))
        s.listen(1)
        try:
            port = find_available_port(start_port=54340, max_attempts=5)
            assert port == 54341
        finally:
            s.close()

    def test_default_start_port(self) -> None:
        """find_available_port with default args should return a port."""
        # Just verify it doesn't crash with defaults; we can't guarantee 3141 is free
        with patch("aspara.cli.socket.socket") as mock_socket_cls:
            mock_sock = mock_socket_cls.return_value
            mock_sock.__enter__ = lambda self: mock_sock
            mock_sock.__exit__ = lambda self, *args: None
            mock_sock.connect_ex.return_value = 1  # Port available

            port = find_available_port()
            assert port == 3141


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point aspara at a temporary data directory with two projects."""
    data_dir = tmp_path / "aspara-data"
    data_dir.mkdir()
    monkeypatch.setenv("ASPARA_DATA_DIR", str(data_dir))

    # Create real data via the aspara API.
    import aspara
    import aspara.run._api as _api

    aspara.init(project="proj_a", name="run1")
    aspara.log({"loss": 0.5}, step=0)
    aspara.finish(quiet=True)

    aspara.init(project="proj_a", name="run2")
    aspara.log({"loss": 0.4}, step=0)
    # Leave run2 as WIP: clear _current_run without finishing so the next
    # init() call does not auto-finish it.
    _api._current_run = None

    aspara.init(project="proj_b", name="run3")
    aspara.log({"loss": 0.3}, step=0)
    aspara.finish(quiet=True)

    return data_dir


class TestVersion:
    """Tests for the ``--version`` flag."""

    def test_get_version_returns_nonempty_string(self) -> None:
        """_get_version returns a non-empty version string."""
        version = _get_version()
        assert isinstance(version, str)
        assert version  # non-empty

    def test_version_flag_prints_version_and_exits_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``aspara --version`` prints ``aspara <version>`` and exits 0."""
        monkeypatch.setattr(sys, "argv", ["aspara", "--version"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "aspara" in captured.out
        assert _get_version() in captured.out

    def test_no_subcommand_exits_nonzero(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``aspara`` without a subcommand exits with a non-zero code."""
        monkeypatch.setattr(sys, "argv", ["aspara"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code != 0


class TestProjectsList:
    """Tests for ``aspara projects``."""

    def test_projects_lists_all_projects(
        self,
        isolated_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["aspara", "projects"])
        main()
        out = capsys.readouterr().out
        assert "proj_a" in out
        assert "proj_b" in out

    def test_projects_shows_run_counts(
        self,
        isolated_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["aspara", "projects"])
        main()
        out = capsys.readouterr().out
        # proj_a has 2 runs, proj_b has 1 run
        assert "2" in out

    def test_projects_empty_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When no projects exist, a helpful message is shown."""
        data_dir = tmp_path / "empty"
        data_dir.mkdir()
        monkeypatch.setenv("ASPARA_DATA_DIR", str(data_dir))
        monkeypatch.setattr(sys, "argv", ["aspara", "projects"])
        main()
        out = capsys.readouterr().out
        assert "No projects" in out or "no projects" in out.lower()


class TestRunsList:
    """Tests for ``aspara runs <project>``."""

    def test_runs_lists_all_runs_in_project(
        self,
        isolated_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["aspara", "runs", "proj_a"])
        main()
        out = capsys.readouterr().out
        assert "run1" in out
        assert "run2" in out

    def test_runs_shows_status(
        self,
        isolated_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The runs list should show run status (Running/Completed)."""
        monkeypatch.setattr(sys, "argv", ["aspara", "runs", "proj_a"])
        main()
        out = capsys.readouterr().out
        assert "Running" in out or "WIP" in out or "wip" in out
        assert "Completed" in out or "completed" in out

    def test_runs_nonexistent_project_exits_nonzero(
        self,
        isolated_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``aspara runs <nonexistent>`` should exit with non-zero code."""
        monkeypatch.setattr(sys, "argv", ["aspara", "runs", "nonexistent"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_runs_missing_project_arg_exits_nonzero(
        self,
        isolated_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``aspara runs`` without a project argument should error."""
        monkeypatch.setattr(sys, "argv", ["aspara", "runs"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0
