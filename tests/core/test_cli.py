"""Unit tests for CLI helper functions in aspara.cli."""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from aspara.cli import _get_version, _resolve_and_validate_data_dir, _warn_wildcard_host, find_available_port, get_default_port, main, parse_serve_components


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


class TestWarnWildcardHost:
    """Tests for _warn_wildcard_host()."""

    def test_localhost_no_warning(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """127.0.0.1 should not produce any warning."""
        _warn_wildcard_host("127.0.0.1")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_wildcard_ipv4_warns(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """0.0.0.0 should produce a security warning."""
        _warn_wildcard_host("0.0.0.0")
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "wildcard" in captured.out

    def test_wildcard_ipv6_warns(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """:: should produce a security warning."""
        _warn_wildcard_host("::")
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_empty_string_warns(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Empty host string should produce a security warning."""
        _warn_wildcard_host("")
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_readonly_mode_no_readonly_hint(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When ASPARA_READ_ONLY=1, the read-only hint is omitted."""
        monkeypatch.setenv("ASPARA_READ_ONLY", "1")
        _warn_wildcard_host("0.0.0.0")
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "read-only" not in captured.out.lower()

    def test_write_mode_shows_readonly_hint(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When not read-only, the hint to enable read-only is shown."""
        monkeypatch.delenv("ASPARA_READ_ONLY", raising=False)
        _warn_wildcard_host("0.0.0.0")
        captured = capsys.readouterr()
        assert "ASPARA_READ_ONLY=1" in captured.out


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


class TestResolveAndValidateDataDir:
    """Tests for _resolve_and_validate_data_dir()."""

    def test_none_falls_back_to_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When data_dir is None, falls back to get_data_dir()."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))
        result = _resolve_and_validate_data_dir(None, require_writable=True)
        assert result == str(tmp_path)

    def test_existing_writable_dir(self, tmp_path: Path) -> None:
        """An existing writable directory passes all checks."""
        result = _resolve_and_validate_data_dir(str(tmp_path), require_writable=True)
        assert result == str(tmp_path.resolve())

    def test_nonexistent_dir_with_existing_parent(self, tmp_path: Path) -> None:
        """A nonexistent dir under an existing parent is accepted (will be created)."""
        target = tmp_path / "new_data_dir"
        result = _resolve_and_validate_data_dir(str(target), require_writable=True)
        assert result == str(target.resolve())

    def test_nonexistent_parent_exits_nonzero(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A path whose parent does not exist causes sys.exit(1)."""
        target = tmp_path / "nonexistent_parent" / "data_dir"
        with pytest.raises(SystemExit) as exc_info:
            _resolve_and_validate_data_dir(str(target), require_writable=False)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "parent does not exist" in captured.out

    def test_unwritable_dir_exits_nonzero(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A directory without write permission causes sys.exit(1)."""
        import os

        read_only = tmp_path / "readonly"
        read_only.mkdir()
        os.chmod(str(read_only), 0o555)  # r-xr-xr-x
        try:
            with pytest.raises(SystemExit) as exc_info:
                _resolve_and_validate_data_dir(str(read_only), require_writable=True)
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "not writable" in captured.out
        finally:
            os.chmod(str(read_only), 0o755)  # restore for cleanup

    def test_forbidden_system_path_exits_nonzero(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A forbidden system path causes sys.exit(1)."""
        with pytest.raises(SystemExit) as exc_info:
            _resolve_and_validate_data_dir("/etc", require_writable=False)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "system directory" in captured.out

    def test_require_writable_false_skips_write_test(self, tmp_path: Path) -> None:
        """require_writable=False skips the write test (read-only commands)."""
        import os

        read_only = tmp_path / "readonly"
        read_only.mkdir()
        os.chmod(str(read_only), 0o555)
        try:
            # Should not raise — write test is skipped
            result = _resolve_and_validate_data_dir(str(read_only), require_writable=False)
            assert result == str(read_only.resolve())
        finally:
            os.chmod(str(read_only), 0o755)

    def test_expands_user_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """~ in the path is expanded."""
        monkeypatch.setenv("HOME", str(tmp_path))
        target = "~/aspara_data"
        result = _resolve_and_validate_data_dir(target, require_writable=False)
        assert result == str((tmp_path / "aspara_data").resolve())
