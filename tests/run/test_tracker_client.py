"""Tests for the Tracker HTTP client."""

from unittest.mock import MagicMock, patch

import requests


class TestTrackerClientSession:
    def test_tracker_client_close_and_context_manager(self):
        """Test TrackerClient.close() and context manager protocol."""
        from aspara.run._tracker_client import TrackerClient

        # Patch requests.Session to track close() calls
        with patch("aspara.run._tracker_client.requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            client = TrackerClient("http://localhost:3142")
            client.close()
            mock_session.close.assert_called_once()

            # Context manager should also close
            mock_session.reset_mock()
            with TrackerClient("http://localhost:3142") as ctx:
                assert ctx is not None
            mock_session.close.assert_called_once()


class TestTrackerClientHealthCheck:
    """Test suite for TrackerClient.health_check method."""

    def test_health_check_success(self, monkeypatch):
        """Test health check returns True on success."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        assert client.health_check() is True
        mock_session.get.assert_called_once_with("http://localhost:3142/api/v1/health", timeout=5.0)

    def test_health_check_failure_status(self, monkeypatch):
        """Test health check returns False on non-200 status."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.get.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        assert client.health_check() is False

    def test_health_check_exception(self, monkeypatch):
        """Test health check returns False on exception."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_session.get.side_effect = requests.RequestException("Connection refused")

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        assert client.health_check() is False

    def test_health_check_custom_timeout(self, monkeypatch):
        """Test health check uses custom timeout."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.health_check(timeout=2.0)
        mock_session.get.assert_called_once_with("http://localhost:3142/api/v1/health", timeout=2.0)


class TestTrackerClientTimeout:
    """Test suite for TrackerClient timeout settings."""

    def test_default_timeout_constant_exists(self):
        """Test that _DEFAULT_TIMEOUT constant is defined."""
        from aspara.run._tracker_client import _DEFAULT_TIMEOUT

        assert _DEFAULT_TIMEOUT == 30.0

    def test_create_run_uses_timeout(self, monkeypatch):
        """Test that create_run passes timeout to requests."""
        from aspara.run._tracker_client import _DEFAULT_TIMEOUT, TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"run_id": "test-123", "name": "test_run"}
        mock_session.post.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.create_run("test_run", "test_project", {}, [], None)

        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs.get("timeout") == _DEFAULT_TIMEOUT

    def test_save_metrics_uses_timeout(self, monkeypatch):
        """Test that save_metrics passes timeout to requests."""
        from aspara.run._tracker_client import _DEFAULT_TIMEOUT, TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_session.post.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.save_metrics("test_project", "test_run", 0, {"loss": 0.5})

        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs.get("timeout") == _DEFAULT_TIMEOUT


class TestTrackerClientURLEncoding:
    """Test suite for TrackerClient URL encoding."""

    def test_create_run_encodes_project(self):
        """Test that create_run URL-encodes the project name."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"run_id": "test-123", "name": "test_run"}
        mock_session.post.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.create_run("test_run", "project/with/slashes", {}, [], None)

        call_url = mock_session.post.call_args[0][0]
        assert "project%2Fwith%2Fslashes" in call_url
        assert "project/with/slashes" not in call_url

    def test_save_metrics_encodes_project_and_run_name(self):
        """Test that save_metrics URL-encodes project and run_name."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_session.post.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.save_metrics("project/special", "run/name", 0, {"loss": 0.5})

        call_url = mock_session.post.call_args[0][0]
        assert "project%2Fspecial" in call_url
        assert "run%2Fname" in call_url

    def test_log_config_encodes_project_and_run_name(self):
        """Test that log_config URL-encodes the project and run_name."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_session.post.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.log_config("project/special", "run/name", {"key": "value"})

        call_url = mock_session.post.call_args[0][0]
        assert "project%2Fspecial" in call_url
        assert "run%2Fname" in call_url

    def test_finish_run_encodes_project_and_run_name(self):
        """Test that finish_run URL-encodes the project and run_name."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_session.post.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.finish_run("project/special", "run/name", 0)

        call_url = mock_session.post.call_args[0][0]
        assert "project%2Fspecial" in call_url
        assert "run%2Fname" in call_url

    def test_update_tags_encodes_project_and_run_name(self):
        """Test that update_tags URL-encodes the project and run_name."""
        from aspara.run._tracker_client import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_session.post.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.update_tags("project/special", "run/name", ["tag1"])

        call_url = mock_session.post.call_args[0][0]
        assert "project%2Fspecial" in call_url
        assert "run%2Fname" in call_url
        call_json = mock_session.post.call_args[1]["json"]
        assert call_json == {"tags": ["tag1"]}
