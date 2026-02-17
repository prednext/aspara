"""
Tests for the Run class and module-level API.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from aspara.run import Config, Run, finish, get_current_run, init, log
from aspara.run._local_run import LocalRun


def read_metadata(temp_dir: str, project: str, run_name: str) -> dict:
    """Read metadata from .meta.json file."""
    metadata_path = Path(temp_dir) / project / f"{run_name}.meta.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            return json.load(f)
    return {}


def read_metrics(temp_dir: str, project: str, run_name: str) -> list:
    """Read metrics from .jsonl file."""
    jsonl_path = Path(temp_dir) / project / f"{run_name}.jsonl"
    metrics = []
    if jsonl_path.exists():
        with open(jsonl_path) as f:
            for line in f:
                if line.strip():
                    metrics.append(json.loads(line.strip()))
    return metrics


class TestRunBasic:
    """Test suite for basic Run functionality."""

    def test_run_init_with_defaults(self):
        """Test Run initialization with default values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            assert run.name == "test_run"
            assert run.project == "default"
            assert run.tags == []
            assert run.id is not None
            assert len(run.id) == 16

    def test_run_init_with_all_params(self):
        """Test Run initialization with all parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(
                name="my_run",
                project="my_project",
                config={"lr": 0.01, "batch_size": 32},
                tags=["test", "baseline"],
                dir=temp_dir,
            )

            assert run.name == "my_run"
            assert run.project == "my_project"
            assert run.config["lr"] == 0.01
            assert run.config["batch_size"] == 32
            assert run.tags == ["test", "baseline"]

    def test_run_auto_name_generation(self):
        """Test that run name is auto-generated if not provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(dir=temp_dir)

            assert run.name is not None
            assert "-" in run.name  # Format: adjective-noun-number

    def test_run_log_basic(self):
        """Test basic metric logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            run.log({"loss": 0.5, "accuracy": 0.95})

            metrics = read_metrics(temp_dir, "default", "test_run")
            assert len(metrics) > 0
            metrics_entry = metrics[0]
            assert metrics_entry["metrics"]["loss"] == 0.5
            assert metrics_entry["metrics"]["accuracy"] == 0.95
            assert metrics_entry["step"] == 0

    def test_run_log_with_step(self):
        """Test metric logging with explicit step."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            run.log({"loss": 0.5}, step=10)

            metrics = read_metrics(temp_dir, "default", "test_run")
            assert len(metrics) > 0
            assert metrics[0]["step"] == 10

    def test_run_log_auto_increment_step(self):
        """Test that step auto-increments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            run.log({"loss": 0.5})
            run.log({"loss": 0.4})
            run.log({"loss": 0.3})

            metrics = read_metrics(temp_dir, "default", "test_run")
            steps = [m["step"] for m in metrics]
            assert steps == [0, 1, 2]

    def test_run_log_with_custom_timestamp(self):
        """Test metric logging with custom timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            custom_timestamp = "2024-01-01T12:00:00"
            run.log({"loss": 0.5}, timestamp=custom_timestamp)

            metrics = read_metrics(temp_dir, "default", "test_run")
            assert len(metrics) > 0
            # Timestamp is normalized to UNIX milliseconds
            # 2024-01-01T12:00:00 in UTC = 1704110400000 ms
            assert metrics[0]["timestamp"] == 1704110400000

    def test_run_log_without_timestamp_uses_current_time(self):
        """Test that logging without timestamp uses current time."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            run.log({"loss": 0.5})

            metrics = read_metrics(temp_dir, "default", "test_run")
            assert len(metrics) > 0
            assert "timestamp" in metrics[0]
            # Timestamp should be UNIX ms (integer)
            assert isinstance(metrics[0]["timestamp"], int)
            assert metrics[0]["timestamp"] > 0

    def test_run_finish(self):
        """Test run finish."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            run.log({"loss": 0.5})
            run.finish(exit_code=0)

            metadata = read_metadata(temp_dir, "default", "test_run")
            assert metadata["is_finished"] is True
            assert metadata["exit_code"] == 0

    def test_run_log_after_finish_raises(self):
        """Test that logging after finish raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)
            run.finish()

            with pytest.raises(RuntimeError, match="Cannot log to a finished run"):
                run.log({"loss": 0.5})


class TestConfig:
    """Test suite for Config class."""

    def test_config_init_empty(self):
        """Test Config initialization without data."""
        config = Config()
        assert config.to_dict() == {}

    def test_config_init_with_data(self):
        """Test Config initialization with data."""
        config = Config({"lr": 0.01, "batch_size": 32})
        assert config["lr"] == 0.01
        assert config["batch_size"] == 32

    def test_config_attribute_access(self):
        """Test Config attribute access."""
        config = Config({"lr": 0.01})
        assert config.lr == 0.01

    def test_config_attribute_set(self):
        """Test Config attribute setting."""
        config = Config()
        config.lr = 0.01
        assert config.lr == 0.01
        assert config["lr"] == 0.01

    def test_config_update(self):
        """Test Config update method."""
        config = Config({"lr": 0.01})
        config.update({"batch_size": 32})
        assert config["lr"] == 0.01
        assert config["batch_size"] == 32

    def test_config_missing_attribute(self):
        """Test Config raises AttributeError for missing attribute."""
        config = Config()
        with pytest.raises(AttributeError, match="Config has no attribute"):
            _ = config.missing


class TestSummary:
    """Test suite for Summary class."""

    def test_summary_set_and_get(self):
        """Test Summary set and get."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            run.summary["best_accuracy"] = 0.99
            assert run.summary["best_accuracy"] == 0.99

    def test_summary_update(self):
        """Test Summary update method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            run.summary.update({"best_accuracy": 0.99, "final_loss": 0.01})
            assert run.summary["best_accuracy"] == 0.99
            assert run.summary["final_loss"] == 0.01

    def test_summary_writes_to_file(self):
        """Test that Summary writes to metadata file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)
            run.summary["best_accuracy"] = 0.99

            metadata = read_metadata(temp_dir, "default", "test_run")
            assert metadata["summary"]["best_accuracy"] == 0.99


class TestModuleLevelAPI:
    """Test suite for module-level API (init, log, finish)."""

    def test_init_and_log(self):
        """Test module-level init and log."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = init(project="test_project", name="test_run", dir=temp_dir)

            log({"loss": 0.5})

            assert run.name == "test_run"
            assert get_current_run() is run

            finish()
            assert get_current_run() is None

    def test_init_with_project_tags_writes_project_metadata(self):
        """init with project_tags should write project-level metadata.json with tags."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project = "test_project"

            run = init(project=project, name="test_run", dir=temp_dir, project_tags=["dog", "cat"])
            assert run.project == project

            # Project-level metadata.json should exist with merged tags
            project_metadata_path = Path(temp_dir) / project / "metadata.json"
            assert project_metadata_path.exists()

            with open(project_metadata_path, encoding="utf-8") as f:
                metadata = json.load(f)

            assert metadata["tags"] == ["dog", "cat"]
            assert metadata["created_at"] is not None
            assert metadata["updated_at"] is not None

    def test_multiple_inits_merge_project_tags_and_preserve_created_at(self):
        """Multiple init calls with project_tags should merge tags and keep created_at stable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project = "test_project"

            # First run with initial tags
            init(project=project, name="run1", dir=temp_dir, project_tags=["dog", "cat"])

            project_metadata_path = Path(temp_dir) / project / "metadata.json"
            assert project_metadata_path.exists()

            with open(project_metadata_path, encoding="utf-8") as f:
                first_metadata = json.load(f)

            first_created_at = first_metadata["created_at"]
            first_tags = first_metadata["tags"]
            assert first_tags == ["dog", "cat"]

            # Second run with overlapping and new tags
            init(project=project, name="run2", dir=temp_dir, project_tags=["cat", "rabbit"])

            with open(project_metadata_path, encoding="utf-8") as f:
                second_metadata = json.load(f)

            # created_at should not change, updated_at should
            assert second_metadata["created_at"] == first_created_at
            assert second_metadata["updated_at"] != first_metadata["updated_at"]

            # Tags should be merged without duplicates, order preserved from first + new
            assert second_metadata["tags"] == ["dog", "cat", "rabbit"]

    def test_log_without_init_raises(self):
        """Test that log without init raises error."""
        # Ensure no active run
        finish()

        with pytest.raises(RuntimeError, match="No active run"):
            log({"loss": 0.5})

    def test_multiple_init_finishes_previous(self):
        """Test that multiple init calls finish previous run."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run1 = init(project="test", name="run1", dir=temp_dir)
            run2 = init(project="test", name="run2", dir=temp_dir)

            assert run1._finished is True
            assert get_current_run() is run2

            finish()

    def test_log_with_custom_timestamp(self):
        """Test module-level log with custom timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = init(project="test_project", name="test_run", dir=temp_dir)
            assert run.name == "test_run"
            assert run.project == "test_project"

            custom_timestamp = "2024-06-15T10:30:00"
            log({"loss": 0.5, "accuracy": 0.95}, timestamp=custom_timestamp)

            metrics = read_metrics(temp_dir, "test_project", "test_run")
            assert len(metrics) > 0
            # Timestamp is normalized to UNIX milliseconds
            # 2024-06-15T10:30:00 in UTC = 1718447400000 ms
            assert metrics[0]["timestamp"] == 1718447400000
            assert metrics[0]["metrics"]["loss"] == 0.5
            assert metrics[0]["metrics"]["accuracy"] == 0.95

            finish()

    def test_init_with_tracker_uri_creates_remote_run(self, monkeypatch):
        """Test initialization with tracker_uri creates RemoteRun."""
        from unittest.mock import MagicMock

        from aspara.run._remote_run import RemoteRun

        # Mock TrackerClient to avoid actual HTTP calls
        mock_client = MagicMock()
        mock_client.create_run.return_value = {"run_id": "test-run-123", "name": "test_run"}

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        def mock_tracker_client_init(self, base_url):
            self.base_url = base_url
            self.session = mock_session

        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.__init__", mock_tracker_client_init)
        monkeypatch.setattr(
            "aspara.run._remote_run.TrackerClient.create_run",
            lambda self, name, project, config, tags, notes, project_tags=None: {"run_id": "server-gen-id", "name": name},
        )
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.finish_run", lambda self, *args, **kwargs: None)

        run = init(project="test_project", name="test_run", tracker_uri="http://localhost:3142")

        # Verify Run wraps RemoteRun backend
        assert isinstance(run, Run)
        assert isinstance(run.backend, RemoteRun)
        assert run.name == "test_run"
        assert run.project == "test_project"

        # Verify it can log metrics (should not raise)
        log({"loss": 0.5, "accuracy": 0.95})

        # Cleanup
        finish()

    def test_remote_run_forwards_project_tags_to_tracker(self, monkeypatch):
        """RemoteRun should forward project_tags to TrackerClient.create_run."""
        from unittest.mock import MagicMock

        captured_kwargs: dict = {}

        def mock_tracker_client_init(self, base_url):
            self.base_url = base_url
            self.session = MagicMock()

        def mock_create_run(self, name, project, config, tags, notes, project_tags=None):  # type: ignore[override]
            captured_kwargs.update(
                name=name,
                project=project,
                config=config,
                tags=tags,
                notes=notes,
                project_tags=project_tags,
            )
            return {"run_id": "server-gen-id", "name": name}

        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.__init__", mock_tracker_client_init)
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.create_run", mock_create_run)
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.finish_run", lambda self, *args, **kwargs: None)

        run = init(project="test_project", name="test_run", tracker_uri="http://localhost:3142", project_tags=["dog", "cat"])  # noqa: F841

        assert captured_kwargs["name"] == "test_run"
        assert captured_kwargs["project"] == "test_project"
        assert captured_kwargs["project_tags"] == ["dog", "cat"]

    def test_remote_run_logs_metrics_to_new_endpoint(self, monkeypatch):
        """RemoteRun.log should POST metrics to /api/v1/projects/{project}/runs/{name}/metrics."""
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        def mock_tracker_client_init(self, base_url):
            self.base_url = base_url
            self.session = mock_session

        def mock_create_run(self, name, project, config, tags, notes, project_tags=None):  # type: ignore[override]
            return {"run_id": "server-gen-id", "name": name}

        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.__init__", mock_tracker_client_init)
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.create_run", mock_create_run)
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.finish_run", lambda self, *args, **kwargs: None)

        _run = init(project="test_project", name="test_run", tracker_uri="http://localhost:3142/tracker")

        # Log metrics and verify URL
        log({"loss": 0.5})

        mock_session.post.assert_called()
        called_url = mock_session.post.call_args[0][0]
        assert called_url == "http://localhost:3142/tracker/api/v1/projects/test_project/runs/test_run/metrics"

    def test_remote_run_forwards_timestamp_to_tracker(self, monkeypatch):
        """RemoteRun.log should forward timestamp parameter to tracker payload when provided."""
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        def mock_tracker_client_init(self, base_url):
            self.base_url = base_url
            self.session = mock_session

        def mock_create_run(self, name, project, config, tags, notes, project_tags=None):  # type: ignore[override]
            return {"run_id": "server-gen-id", "name": name}

        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.__init__", mock_tracker_client_init)
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.create_run", mock_create_run)
        monkeypatch.setattr("aspara.run._remote_run.TrackerClient.finish_run", lambda self, *args, **kwargs: None)

        # Initialize RemoteRun via init()
        _run = init(project="test_project", name="test_run", tracker_uri="http://localhost:3142/tracker")

        # Log with explicit timestamp
        custom_ts = "2024-06-15T10:30:00"
        log({"loss": 0.5}, timestamp=custom_ts)

        # Verify timestamp was forwarded in JSON payload
        mock_session.post.assert_called()
        _, kwargs = mock_session.post.call_args
        payload = kwargs["json"]
        assert payload["timestamp"] == custom_ts


class TestRunArtifacts:
    """Test suite for Run class artifact functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_file.txt")

        with open(self.test_file, "w") as f:
            f.write("Test content for artifact")

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_artifact_basic(self):
        """Test basic artifact logging functionality."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            run.log_artifact(self.test_file)

            artifacts_dir = os.path.join(temp_output_dir, "default", "test_run", "artifacts")
            artifact_path = os.path.join(artifacts_dir, "test_file.txt")
            assert os.path.exists(artifact_path)

            with open(artifact_path) as f:
                content = f.read()
            assert content == "Test content for artifact"

            metadata = read_metadata(temp_output_dir, "default", "test_run")
            artifacts = metadata.get("artifacts", [])
            assert len(artifacts) > 0
            artifact_entry = artifacts[0]
            assert artifact_entry["name"] == "test_file.txt"
            assert artifact_entry["stored_path"] == "artifacts/test_file.txt"
            assert artifact_entry["file_size"] > 0

    def test_log_artifact_with_custom_name(self):
        """Test artifact logging with custom name."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            run.log_artifact(self.test_file, name="custom_name.txt")

            artifacts_dir = os.path.join(temp_output_dir, "default", "test_run", "artifacts")
            artifact_path = os.path.join(artifacts_dir, "custom_name.txt")
            assert os.path.exists(artifact_path)

            metadata = read_metadata(temp_output_dir, "default", "test_run")
            artifacts = metadata.get("artifacts", [])
            assert len(artifacts) > 0
            assert artifacts[0]["name"] == "custom_name.txt"

    def test_log_artifact_with_description_and_category(self):
        """Test artifact logging with description and category."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            run.log_artifact(self.test_file, description="Test configuration file", category="config")

            metadata = read_metadata(temp_output_dir, "default", "test_run")
            artifacts = metadata.get("artifacts", [])
            assert len(artifacts) > 0
            artifact_entry = artifacts[0]
            assert artifact_entry["description"] == "Test configuration file"
            assert artifact_entry["category"] == "config"

    def test_log_artifact_file_not_exists(self):
        """Test error handling when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            with pytest.raises(ValueError, match="File does not exist"):
                run.log_artifact("/non/existent/file.txt")

    def test_log_artifact_empty_file_path(self):
        """Test error handling for empty file path."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            with pytest.raises(ValueError, match="File path cannot be empty"):
                run.log_artifact("")

    def test_log_artifact_directory_path(self):
        """Test error handling when path is a directory."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            with pytest.raises(ValueError, match="Path is not a file"):
                run.log_artifact(self.temp_dir)

    def test_log_artifact_invalid_category(self):
        """Test error handling for invalid category."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            with pytest.raises(ValueError, match="Invalid category"):
                run.log_artifact(self.test_file, category="invalid_category")

    def test_log_artifact_valid_categories(self):
        """Test that all valid categories are accepted."""
        valid_categories = ["code", "model", "config", "data", "other"]

        for category in valid_categories:
            with tempfile.TemporaryDirectory() as temp_output_dir:
                run = Run(name="test_run", dir=temp_output_dir)

                run.log_artifact(self.test_file, category=category)

                metadata = read_metadata(temp_output_dir, "default", "test_run")
                artifacts = metadata.get("artifacts", [])
                assert len(artifacts) > 0
                assert artifacts[0]["category"] == category

    def test_artifacts_directory_creation(self):
        """Test that artifacts directory is created automatically."""
        with tempfile.TemporaryDirectory() as temp_output_dir:
            run = Run(name="test_run", dir=temp_output_dir)

            artifacts_dir = os.path.join(temp_output_dir, "default", "test_run", "artifacts")
            assert not os.path.exists(artifacts_dir)

            run.log_artifact(self.test_file)

            assert os.path.exists(artifacts_dir)
            assert os.path.isdir(artifacts_dir)


class TestRunFactory:
    """Test suite for Run composition pattern."""

    def test_run_factory_uses_localrun_backend_without_tracker_uri(self):
        """Test that Run() uses LocalRun backend when tracker_uri is not provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir)

            # Should be Run instance with LocalRun backend
            assert isinstance(run, Run)
            assert isinstance(run.backend, LocalRun)
            assert run.name == "test_run"
            assert run.project == "default"

    def test_run_factory_uses_localrun_backend_with_none_tracker_uri(self):
        """Test that Run() uses LocalRun backend when tracker_uri is explicitly None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Run(name="test_run", dir=temp_dir, tracker_uri=None)

            # Should be Run instance with LocalRun backend
            assert isinstance(run, Run)
            assert isinstance(run.backend, LocalRun)
            assert run.name == "test_run"

    def test_localrun_direct_instantiation(self):
        """Test that LocalRun can be directly instantiated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = LocalRun(name="test_run", dir=temp_dir)

            assert isinstance(run, LocalRun)
            assert run.name == "test_run"
            assert run.project == "default"

    def test_localrun_has_same_functionality_as_old_run(self):
        """Test that LocalRun has the same functionality as the old Run class."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run = LocalRun(name="test_run", dir=temp_dir, config={"lr": 0.01})

            # Test basic functionality
            run.log({"loss": 0.5})
            run.config["batch_size"] = 32
            run.summary["best_loss"] = 0.3
            run.finish()

            # Verify metadata was written
            metadata = read_metadata(temp_dir, "default", "test_run")
            assert metadata["config"]["lr"] == 0.01
            assert metadata["config"]["batch_size"] == 32
            assert metadata["summary"]["best_loss"] == 0.3


class TestContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_basic(self):
        """Context manager calls finish automatically."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with Run(name="test_cm", dir=temp_dir) as run:
                run.log({"loss": 0.5})
            assert run._finished is True

    def test_context_manager_exception(self):
        """Context manager calls finish even on exception."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            pytest.raises(ValueError),
            Run(name="test_cm_exc", dir=temp_dir) as run,
        ):
            run.log({"loss": 0.5})
            raise ValueError("test error")
        assert run._finished is True

    def test_context_manager_exit_code_on_exception(self):
        """Context manager sets exit_code=1 when exception occurs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError), Run(name="test_cm_exit", dir=temp_dir) as run:
                run.log({"loss": 0.5})
                raise ValueError("test error")

            metadata = read_metadata(temp_dir, "default", "test_cm_exit")
            assert metadata["exit_code"] == 1

    def test_context_manager_exit_code_on_success(self):
        """Context manager sets exit_code=0 on normal exit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with Run(name="test_cm_success", dir=temp_dir) as run:
                run.log({"loss": 0.5})

            metadata = read_metadata(temp_dir, "default", "test_cm_success")
            assert metadata["exit_code"] == 0

    def test_context_manager_cannot_log_after_exit(self):
        """Cannot log after exiting context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with Run(name="test_cm_log", dir=temp_dir) as run:
                run.log({"loss": 0.5})
            with pytest.raises(RuntimeError, match="Cannot log to a finished run"):
                run.log({"loss": 0.3})

    def test_context_manager_manual_finish(self):
        """Manual finish inside context is safe."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with Run(name="test_cm_manual", dir=temp_dir) as run:
                run.log({"loss": 0.5})
                run.finish()  # Manual finish
            # __exit__ calls finish again, but idempotent
            assert run._finished is True
