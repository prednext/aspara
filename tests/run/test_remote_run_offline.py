"""Integration tests for RemoteRun with offline queue functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRemoteRunOfflineQueue:
    """Test suite for RemoteRun offline queue integration."""

    @pytest.fixture
    def mock_tracker_client(self, monkeypatch):
        """Create a mock TrackerClient for testing."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session.get.return_value = mock_response

        def mock_tracker_client_init(self, base_url):
            self.base_url = base_url
            self.session = mock_session

        def mock_create_run(self, name, project, config, tags, notes, project_tags=None):
            return {"run_id": "server-gen-id", "name": name}

        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.__init__", mock_tracker_client_init)
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.create_run", mock_create_run)
        monkeypatch.setattr(
            "aspara.run._remote_run.TrackerClient.finish_run",
            lambda self, *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "aspara.run._remote_run.TrackerClient.health_check",
            lambda self, timeout=5.0: True,
        )

        return mock_session

    @pytest.fixture
    def temp_data_dir(self, monkeypatch):
        """Create a temporary data directory for queue storage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monkeypatch.setattr("aspara.run._offline_queue.get_data_dir", lambda: Path(temp_dir))
            yield Path(temp_dir)

    def test_remote_run_initializes_offline_queue(self, mock_tracker_client, temp_data_dir):
        """Test that RemoteRun initializes offline queue on creation."""
        from aspara.run._remote_run import RemoteRun

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        assert run._queue_storage is not None
        assert run._retry_worker is not None
        assert run._retry_worker._thread is not None
        assert run._retry_worker._thread.is_alive()

        run.finish(quiet=True)

    def test_remote_run_queues_metrics_on_failure(self, mock_tracker_client, temp_data_dir):
        """Test that metrics are queued when tracker is unavailable."""
        from aspara.run._remote_run import RemoteRun

        # Make save_metrics fail
        mock_tracker_client.post.side_effect = Exception("Connection refused")

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        # Log some metrics (should queue on failure)
        run.log({"loss": 0.5})
        run.log({"loss": 0.4})
        run.log({"loss": 0.3})

        # Verify metrics were queued
        assert run._queue_storage.count() == 3

        run.finish(quiet=True, flush_timeout=0.1)

    def test_remote_run_finish_flushes_queue(self, mock_tracker_client, temp_data_dir):
        """Test that finish() flushes the offline queue."""
        from aspara.run._remote_run import RemoteRun

        # Track sent metrics
        sent_metrics = []

        def mock_save_metrics(project, run_name, step, metrics, timestamp=None):
            sent_metrics.append((step, metrics))
            return {}

        # First make save_metrics fail to queue metrics
        mock_tracker_client.post.side_effect = Exception("Connection refused")

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        # Log some metrics (will be queued)
        run.log({"loss": 0.5})
        run.log({"loss": 0.4})

        assert run._queue_storage.count() == 2

        # Now make save_metrics succeed for flush
        mock_tracker_client.post.side_effect = None
        mock_tracker_client.post.return_value = MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value={}))

        # Patch client methods directly before finish
        run.client.save_metrics = mock_save_metrics
        run.client.health_check = lambda timeout=5.0: True
        # Reset health check cache
        run._retry_worker._last_health_result = True
        run._retry_worker._last_health_check = 0

        run.finish(quiet=True)

        # Verify metrics were sent during flush
        assert len(sent_metrics) == 2
        assert run._queue_storage.is_empty()

    def test_remote_run_flush_method(self, mock_tracker_client, temp_data_dir):
        """Test that flush() method sends queued metrics."""
        from aspara.run._remote_run import RemoteRun

        # Make save_metrics fail initially
        mock_tracker_client.post.side_effect = Exception("Connection refused")

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        # Log metrics (will be queued)
        run.log({"loss": 0.5})

        assert run._queue_storage.count() == 1

        # Make save_metrics succeed
        mock_tracker_client.post.side_effect = None
        mock_tracker_client.post.return_value = MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value={}))

        with patch.object(run.client, "save_metrics", return_value={}), patch.object(run.client, "health_check", return_value=True):
            failed = run.flush(timeout=5.0)

        assert failed == 0
        assert run._queue_storage.is_empty()

        run.finish(quiet=True)

    def test_remote_run_successful_log_not_queued(self, mock_tracker_client, temp_data_dir):
        """Test that successful log() calls don't queue metrics."""
        from aspara.run._remote_run import RemoteRun

        # Make save_metrics succeed
        mock_tracker_client.post.return_value = MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value={}))

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        # Log metrics (should succeed and not queue)
        run.log({"loss": 0.5})
        run.log({"loss": 0.4})

        # Verify metrics were not queued
        assert run._queue_storage.is_empty()

        run.finish(quiet=True)

    def test_remote_run_worker_retries_queued_metrics(self, mock_tracker_client, temp_data_dir):
        """Test that the worker retries queued metrics."""
        from aspara.run._remote_run import RemoteRun

        # Make save_metrics fail initially
        mock_tracker_client.post.side_effect = Exception("Connection refused")

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        # Log metrics (will be queued)
        run.log({"loss": 0.5})

        assert run._queue_storage.count() == 1

        # Make save_metrics succeed
        mock_tracker_client.post.side_effect = None
        mock_tracker_client.post.return_value = MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value={}))

        with patch.object(run.client, "save_metrics", return_value={}), patch.object(run.client, "health_check", return_value=True):
            # Trigger worker processing manually
            run._retry_worker._process_queue()

        # Verify queue is empty after retry
        assert run._queue_storage.is_empty()

        run.finish(quiet=True)

    def test_remote_run_stops_worker_on_finish(self, mock_tracker_client, temp_data_dir):
        """Test that finish() stops the retry worker."""
        from aspara.run._remote_run import RemoteRun

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        thread = run._retry_worker._thread
        assert thread is not None
        assert thread.is_alive()

        run.finish(quiet=True)

        # Worker should be stopped and thread set to None
        assert not thread.is_alive()
        assert run._retry_worker._thread is None

    def test_remote_run_queue_preserves_timestamp(self, mock_tracker_client, temp_data_dir):
        """Test that queued metrics preserve the timestamp."""
        from aspara.run._remote_run import RemoteRun

        # Make save_metrics fail
        mock_tracker_client.post.side_effect = Exception("Connection refused")

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        custom_timestamp = "2024-01-01T12:00:00"
        run.log({"loss": 0.5}, timestamp=custom_timestamp)

        # Verify the queued item has the timestamp
        items = run._queue_storage.get_ready_items()
        assert len(items) == 1
        assert items[0].timestamp == custom_timestamp

        run.finish(quiet=True, flush_timeout=0.1)

    def test_remote_run_queue_preserves_step(self, mock_tracker_client, temp_data_dir):
        """Test that queued metrics preserve the step number."""
        from aspara.run._remote_run import RemoteRun

        # Make save_metrics fail
        mock_tracker_client.post.side_effect = Exception("Connection refused")

        run = RemoteRun(
            name="test_run",
            project="test_project",
            tracker_uri="http://localhost:3142",
        )

        run.log({"loss": 0.5}, step=10)
        run.log({"loss": 0.4}, step=20)

        items = run._queue_storage.get_ready_items()
        assert len(items) == 2
        steps = [item.step for item in items]
        assert steps == [10, 20]

        run.finish(quiet=True, flush_timeout=0.1)


class TestTrackerClientHealthCheck:
    """Test suite for TrackerClient.health_check method."""

    def test_health_check_success(self, monkeypatch):
        """Test health check returns True on success."""
        from aspara.run._remote_run import TrackerClient

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
        from aspara.run._remote_run import TrackerClient

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
        from aspara.run._remote_run import TrackerClient

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection refused")

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        assert client.health_check() is False

    def test_health_check_custom_timeout(self, monkeypatch):
        """Test health check uses custom timeout."""
        from aspara.run._remote_run import TrackerClient

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        client = TrackerClient.__new__(TrackerClient)
        client.base_url = "http://localhost:3142"
        client.session = mock_session

        client.health_check(timeout=2.0)
        mock_session.get.assert_called_once_with("http://localhost:3142/api/v1/health", timeout=2.0)


class TestQueueFileStructure:
    """Test suite for queue file structure."""

    def test_queue_files_location(self, monkeypatch):
        """Test that queue files are created in the correct location."""
        from aspara.run._remote_run import RemoteRun

        with tempfile.TemporaryDirectory() as temp_dir:
            monkeypatch.setattr("aspara.run._offline_queue.get_data_dir", lambda: Path(temp_dir))

            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {}
            mock_session.post.return_value = mock_response

            def mock_tracker_client_init(self, base_url):
                self.base_url = base_url
                self.session = mock_session

            monkeypatch.setattr("aspara.run._remote_run.TrackerClient.__init__", mock_tracker_client_init)
            monkeypatch.setattr(
                "aspara.run._remote_run.TrackerClient.create_run",
                lambda self, **kwargs: {"run_id": "test-123", "name": kwargs["name"]},
            )
            monkeypatch.setattr(
                "aspara.run._remote_run.TrackerClient.finish_run",
                lambda self, *args, **kwargs: None,
            )
            monkeypatch.setattr(
                "aspara.run._remote_run.TrackerClient.health_check",
                lambda self, timeout=5.0: True,
            )

            # Make save_metrics fail to trigger queue
            mock_session.post.side_effect = Exception("Connection refused")

            run = RemoteRun(
                name="test_run",
                project="test_project",
                tracker_uri="http://localhost:3142",
            )

            run.log({"loss": 0.5})

            # Check file paths
            queue_dir = Path(temp_dir) / ".queue" / "test_project"
            assert queue_dir.exists()
            assert (queue_dir / "test_run.queue.jsonl").exists()
            assert (queue_dir / "test_run.queue.meta.json").exists()

            run.finish(quiet=True, flush_timeout=0.1)

    def test_queue_metadata_content(self, monkeypatch):
        """Test that queue metadata contains correct information."""
        import json

        from aspara.run._remote_run import RemoteRun

        with tempfile.TemporaryDirectory() as temp_dir:
            monkeypatch.setattr("aspara.run._offline_queue.get_data_dir", lambda: Path(temp_dir))

            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {}
            mock_session.post.return_value = mock_response

            def mock_tracker_client_init(self, base_url):
                self.base_url = base_url
                self.session = mock_session

            monkeypatch.setattr("aspara.run._remote_run.TrackerClient.__init__", mock_tracker_client_init)
            monkeypatch.setattr(
                "aspara.run._remote_run.TrackerClient.create_run",
                lambda self, **kwargs: {"run_id": "test-run-id", "name": kwargs["name"]},
            )
            monkeypatch.setattr(
                "aspara.run._remote_run.TrackerClient.finish_run",
                lambda self, *args, **kwargs: None,
            )
            monkeypatch.setattr(
                "aspara.run._remote_run.TrackerClient.health_check",
                lambda self, timeout=5.0: True,
            )

            run = RemoteRun(
                name="test_run",
                project="test_project",
                tracker_uri="http://localhost:3142",
            )

            # Read metadata file
            meta_file = Path(temp_dir) / ".queue" / "test_project" / "test_run.queue.meta.json"
            with open(meta_file) as f:
                metadata = json.load(f)

            assert metadata["tracker_uri"] == "http://localhost:3142"
            assert metadata["project"] == "test_project"
            assert metadata["run_name"] == "test_run"
            assert metadata["run_id"] == "test-run-id"
            assert "created_at" in metadata

            run.finish(quiet=True)


class TestTrackerClientTimeout:
    """Test suite for TrackerClient timeout settings."""

    def test_default_timeout_constant_exists(self):
        """Test that _DEFAULT_TIMEOUT constant is defined."""
        from aspara.run._remote_run import _DEFAULT_TIMEOUT

        assert _DEFAULT_TIMEOUT == 30.0

    def test_create_run_uses_timeout(self, monkeypatch):
        """Test that create_run passes timeout to requests."""
        from aspara.run._remote_run import _DEFAULT_TIMEOUT, TrackerClient

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
        from aspara.run._remote_run import _DEFAULT_TIMEOUT, TrackerClient

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
        from aspara.run._remote_run import TrackerClient

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
        from aspara.run._remote_run import TrackerClient

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
        from aspara.run._remote_run import TrackerClient

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
        from aspara.run._remote_run import TrackerClient

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
