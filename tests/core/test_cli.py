"""Unit tests for CLI helper functions in aspara.cli."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from aspara.cli import find_available_port, get_default_port, parse_serve_components


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


class TestMainPortNotFound:
    """Tests that main() exits with code 1 when no port is available."""

    def test_main_exits_on_no_port(self) -> None:
        """main() should call sys.exit(1) when find_available_port returns None."""
        from aspara.cli import main

        with (
            patch("aspara.cli.find_available_port", return_value=None),
            patch("sys.argv", ["aspara"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
