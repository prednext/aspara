"""
Tests for RunMetadataStorage.
"""

import json

import pytest

from aspara.storage.metadata import RunMetadataStorage


class TestRunMetadataStorage:
    """Tests for RunMetadataStorage class."""

    def test_init_creates_empty_metadata(self, tmp_path):
        """Test that initialization creates empty metadata structure."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        metadata = storage.get_metadata()
        assert metadata["run_id"] is None
        assert metadata["tags"] == []
        assert metadata["notes"] == ""
        assert metadata["params"] == {}
        assert metadata["config"] == {}
        assert metadata["artifacts"] == []
        assert metadata["summary"] == {}
        assert metadata["is_finished"] is False
        assert metadata["exit_code"] is None

    def test_set_init(self, tmp_path):
        """Test setting initial run metadata."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.set_init(run_id="abc123", tags=["experiment", "test"], timestamp="2024-01-01T00:00:00")

        metadata = storage.get_metadata()
        assert metadata["run_id"] == "abc123"
        assert metadata["tags"] == ["experiment", "test"]
        assert metadata["start_time"] == "2024-01-01T00:00:00"

    def test_update_config(self, tmp_path):
        """Test updating config parameters."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.update_config({"lr": 0.01, "batch_size": 32})
        storage.update_config({"epochs": 10})

        metadata = storage.get_metadata()
        assert metadata["config"] == {"lr": 0.01, "batch_size": 32, "epochs": 10}

    def test_update_params(self, tmp_path):
        """Test updating parameters."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.update_params({"model": "resnet", "optimizer": "adam"})
        storage.update_params({"scheduler": "cosine"})

        metadata = storage.get_metadata()
        assert metadata["params"] == {"model": "resnet", "optimizer": "adam", "scheduler": "cosine"}

    def test_add_artifact(self, tmp_path):
        """Test adding artifact metadata."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.add_artifact({"name": "model.pt", "size": 1024})
        storage.add_artifact({"name": "config.yaml", "size": 256})

        artifacts = storage.get_artifacts()
        assert len(artifacts) == 2
        assert artifacts[0]["name"] == "model.pt"
        assert artifacts[1]["name"] == "config.yaml"

    def test_update_summary(self, tmp_path):
        """Test updating summary data."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.update_summary({"best_acc": 0.95})
        storage.update_summary({"final_loss": 0.05})

        metadata = storage.get_metadata()
        assert metadata["summary"] == {"best_acc": 0.95, "final_loss": 0.05}

    def test_set_finish(self, tmp_path):
        """Test marking run as finished."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.set_finish(exit_code=0, timestamp="2024-01-01T01:00:00")

        metadata = storage.get_metadata()
        assert metadata["is_finished"] is True
        assert metadata["exit_code"] == 0
        assert metadata["finish_time"] == "2024-01-01T01:00:00"

    def test_set_tags(self, tmp_path):
        """Test setting tags (replaces existing)."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.set_init(run_id="abc", tags=["old"])
        storage.set_tags(["new", "tags"])

        assert storage.get_tags() == ["new", "tags"]

    def test_get_params_merges_config_and_params(self, tmp_path):
        """Test that get_params merges both config and params."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")

        storage.update_config({"lr": 0.01})
        storage.update_params({"model": "resnet"})

        params = storage.get_params()
        assert params == {"lr": 0.01, "model": "resnet"}

    def test_persistence_across_instances(self, tmp_path):
        """Test that metadata persists across storage instances."""
        storage1 = RunMetadataStorage(tmp_path, "test_project", "test_run")
        storage1.set_init(run_id="abc123", tags=["test"])
        storage1.update_config({"lr": 0.01})

        storage2 = RunMetadataStorage(tmp_path, "test_project", "test_run")
        metadata = storage2.get_metadata()

        assert metadata["run_id"] == "abc123"
        assert metadata["tags"] == ["test"]
        assert metadata["config"] == {"lr": 0.01}

    def test_metadata_file_location(self, tmp_path):
        """Test that metadata file is created in correct location."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        storage.set_init(run_id="abc123")

        metadata_file = tmp_path / "test_project" / "test_run.meta.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            data = json.load(f)
            assert data["run_id"] == "abc123"

    def test_close_is_noop(self, tmp_path):
        """Test that close() doesn't raise errors."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        storage.close()


class TestRunMetadataStorageValidation:
    """Tests for RunMetadataStorage input validation."""

    def test_invalid_project_name_raises_error(self, tmp_path):
        """Test that invalid project names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid project name"):
            RunMetadataStorage(tmp_path, "../etc/passwd", "test_run")

    def test_invalid_run_name_raises_error(self, tmp_path):
        """Test that invalid run names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid run name"):
            RunMetadataStorage(tmp_path, "test_project", "../etc/passwd")

    def test_empty_project_name_raises_error(self, tmp_path):
        """Test that empty project names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid project name"):
            RunMetadataStorage(tmp_path, "", "test_run")

    def test_empty_run_name_raises_error(self, tmp_path):
        """Test that empty run names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid run name"):
            RunMetadataStorage(tmp_path, "test_project", "")

    def test_set_init_with_non_string_notes_raises_error(self, tmp_path):
        """Test that non-string notes raise ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        with pytest.raises(ValueError, match="notes must be a string"):
            storage.set_init(run_id="abc123", notes=123)  # type: ignore[arg-type]

    def test_set_init_with_too_long_notes_raises_error(self, tmp_path):
        """Test that notes exceeding max length raise ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        long_notes = "a" * (10 * 1024 + 1)  # Default max is 10KB
        with pytest.raises(ValueError, match="notes exceeds maximum length"):
            storage.set_init(run_id="abc123", notes=long_notes)

    def test_set_init_with_non_list_tags_raises_error(self, tmp_path):
        """Test that non-list tags raise ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        with pytest.raises(ValueError, match="tags must be a list"):
            storage.set_init(run_id="abc123", tags="not_a_list")  # type: ignore[arg-type]

    def test_set_init_with_too_many_tags_raises_error(self, tmp_path):
        """Test that tags exceeding max count raise ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        too_many_tags = [f"tag{i}" for i in range(101)]  # Default max is 100
        with pytest.raises(ValueError, match="Too many tags"):
            storage.set_init(run_id="abc123", tags=too_many_tags)

    def test_set_init_with_non_string_tag_raises_error(self, tmp_path):
        """Test that non-string tags raise ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        with pytest.raises(ValueError, match="All tags must be strings"):
            storage.set_init(run_id="abc123", tags=["valid", 123])  # type: ignore[list-item]

    def test_set_tags_with_non_list_raises_error(self, tmp_path):
        """Test that set_tags with non-list raises ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        with pytest.raises(ValueError, match="tags must be a list"):
            storage.set_tags("not_a_list")  # type: ignore[arg-type]

    def test_set_tags_with_too_many_tags_raises_error(self, tmp_path):
        """Test that set_tags with too many tags raises ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        too_many_tags = [f"tag{i}" for i in range(101)]
        with pytest.raises(ValueError, match="Too many tags"):
            storage.set_tags(too_many_tags)

    def test_set_tags_with_non_string_tag_raises_error(self, tmp_path):
        """Test that set_tags with non-string tag raises ValueError."""
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        with pytest.raises(ValueError, match="All tags must be strings"):
            storage.set_tags(["valid", 123])  # type: ignore[list-item]

    def test_load_handles_corrupted_json(self, tmp_path):
        """Test that _load handles corrupted JSON gracefully."""
        # Create a corrupted metadata file
        project_dir = tmp_path / "test_project"
        project_dir.mkdir(parents=True)
        metadata_file = project_dir / "test_run.meta.json"
        metadata_file.write_text("{ invalid json }")

        # Should not raise, just use default values
        storage = RunMetadataStorage(tmp_path, "test_project", "test_run")
        metadata = storage.get_metadata()
        assert metadata["run_id"] is None
        assert metadata["tags"] == []
