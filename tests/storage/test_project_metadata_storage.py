"""
Tests for ProjectMetadataStorage.
"""

import json

import pytest

from aspara.storage.metadata import ProjectMetadataStorage


class TestProjectMetadataStorage:
    """Tests for ProjectMetadataStorage class."""

    def test_init_creates_empty_metadata(self, tmp_path):
        """Test that initialization creates empty metadata structure."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        metadata = storage.get_metadata()
        assert metadata["notes"] == ""
        assert metadata["tags"] == []
        assert metadata["created_at"] is None
        assert metadata["updated_at"] is None

    def test_update_metadata_sets_timestamps(self, tmp_path):
        """Test that update_metadata sets created_at and updated_at."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        result = storage.update_metadata({"notes": "Test project"})

        assert result["notes"] == "Test project"
        assert result["created_at"] is not None
        assert result["updated_at"] is not None
        assert result["created_at"] == result["updated_at"]

    def test_update_metadata_preserves_created_at(self, tmp_path):
        """Test that subsequent updates preserve created_at."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        first_update = storage.update_metadata({"notes": "First"})
        created_at = first_update["created_at"]

        second_update = storage.update_metadata({"notes": "Second"})

        assert second_update["created_at"] == created_at
        assert second_update["updated_at"] != created_at

    def test_update_tags(self, tmp_path):
        """Test updating tags."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        storage.update_metadata({"tags": ["experiment", "test"]})
        metadata = storage.get_metadata()

        assert metadata["tags"] == ["experiment", "test"]

    def test_update_partial_metadata(self, tmp_path):
        """Test that partial updates work correctly."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        storage.update_metadata({"notes": "Initial notes"})
        storage.update_metadata({"tags": ["tag1", "tag2"]})

        metadata = storage.get_metadata()
        assert metadata["notes"] == "Initial notes"
        assert metadata["tags"] == ["tag1", "tag2"]

    def test_persistence_across_instances(self, tmp_path):
        """Test that metadata persists across storage instances."""
        storage1 = ProjectMetadataStorage(tmp_path, "test_project")
        storage1.update_metadata({"notes": "Persistent", "tags": ["test"]})

        storage2 = ProjectMetadataStorage(tmp_path, "test_project")
        metadata = storage2.get_metadata()

        assert metadata["notes"] == "Persistent"
        assert metadata["tags"] == ["test"]

    def test_delete_metadata(self, tmp_path):
        """Test deleting metadata."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")
        storage.update_metadata({"notes": "To be deleted"})

        result = storage.delete_metadata()
        assert result is True

        metadata = storage.get_metadata()
        assert metadata["notes"] == ""
        assert metadata["tags"] == []

    def test_delete_nonexistent_metadata(self, tmp_path):
        """Test deleting metadata that doesn't exist."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        result = storage.delete_metadata()
        assert result is False

    def test_metadata_file_location(self, tmp_path):
        """Test that metadata file is created in correct location."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")
        storage.update_metadata({"notes": "Test"})

        metadata_file = tmp_path / "test_project" / "metadata.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            data = json.load(f)
            assert data["notes"] == "Test"

    def test_validate_notes_length(self, tmp_path):
        """Test that notes length is validated."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        with pytest.raises(ValueError, match="notes exceeds maximum length"):
            storage.update_metadata({"notes": "x" * 100000})

    def test_validate_tags_count(self, tmp_path):
        """Test that tags count is validated."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        with pytest.raises(ValueError, match="Too many tags"):
            storage.update_metadata({"tags": [f"tag{i}" for i in range(1000)]})

    def test_validate_tags_type(self, tmp_path):
        """Test that tags must be strings."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        with pytest.raises(ValueError, match="All tags must be strings"):
            storage.update_metadata({"tags": ["valid", 123, "also_valid"]})

    def test_validate_notes_type(self, tmp_path):
        """Test that notes must be a string."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        with pytest.raises(ValueError, match="notes must be a string"):
            storage.update_metadata({"notes": 123})

    def test_validate_tags_list_type(self, tmp_path):
        """Test that tags must be a list."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")

        with pytest.raises(ValueError, match="tags must be a list"):
            storage.update_metadata({"tags": "not_a_list"})

    def test_close_is_noop(self, tmp_path):
        """Test that close() doesn't raise errors."""
        storage = ProjectMetadataStorage(tmp_path, "test_project")
        storage.close()

    def test_invalid_project_name(self, tmp_path):
        """Test that invalid project names are rejected."""
        with pytest.raises(ValueError):
            ProjectMetadataStorage(tmp_path, "../invalid")
