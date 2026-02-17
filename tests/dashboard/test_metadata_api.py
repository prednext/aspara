"""
Tests for metadata API endpoints.
"""

import tempfile

import pytest
from fastapi.testclient import TestClient

from aspara.dashboard.main import app


@pytest.fixture
def temp_logs_dir():
    """Create a temporary logs directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def client(temp_logs_dir):
    """Create test client with temporary logs directory."""
    # Initialize services with temp directory
    from aspara.dashboard.router import configure_data_dir

    configure_data_dir(temp_logs_dir)

    return TestClient(app)


def test_get_project_metadata_nonexistent(client):
    """Test getting metadata for non-existent project."""
    response = client.get("/api/projects/nonexistent/metadata")
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == ""
    assert data["tags"] == []
    assert data["created_at"] is None
    assert data["updated_at"] is None


def test_update_project_metadata(client):
    """Test updating project metadata."""
    project = "test_project"
    note = "This is a test project note"
    tags = ["test", "project"]

    # Update metadata
    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": note, "tags": tags})
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == note
    assert data["tags"] == tags
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_get_project_metadata_existing(client):
    """Test getting existing project metadata."""
    project = "test_project"
    note = "Existing note"

    # First create the metadata
    client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": note})

    # Then get it
    response = client.get(f"/api/projects/{project}/metadata")
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == note


def test_update_run_metadata(client):
    """Test updating run metadata."""
    project = "test_project"
    run = "test_run"
    note = "Run note with\nmultiple lines"

    response = client.put(f"/api/projects/{project}/runs/{run}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": note})
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == note


def test_partial_metadata_update(client):
    """Test partial metadata updates."""
    project = "test_project"

    # Set initial data
    client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": "Initial note", "tags": ["initial"]})

    # Update only note
    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": "Updated note"})
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == "Updated note"
    assert data["tags"] == ["initial"]  # Should be preserved


def test_invalid_metadata_request(client):
    """Test invalid metadata request validation."""
    project = "test_project"

    # Test invalid note type
    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": 123})
    assert response.status_code == 422  # Validation error


def test_empty_note_update(client):
    """Test updating with empty note."""
    project = "test_project"

    # Set initial note
    client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": "Initial note"})

    # Clear note
    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": ""})
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == ""


def test_unicode_note_handling(client):
    """Test handling of unicode content in note."""
    project = "test_project"
    note = "日本語のメモ with emojis 🚀✨"

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": note})
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == note

    # Verify it can be retrieved correctly
    response = client.get(f"/api/projects/{project}/metadata")
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == note


def test_long_note_handling(client):
    """Test handling of long note content."""
    project = "test_project"
    note = "Very long note content. " * 100  # Create long content

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": note})
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == note


def test_tags_handling(client):
    """Test tags creation and retrieval."""
    project = "test_project"
    tags = ["machine-learning", "experiment", "test", "日本語タグ"]

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": tags})
    assert response.status_code == 200

    data = response.json()
    assert data["tags"] == tags

    # Verify tags are preserved
    response = client.get(f"/api/projects/{project}/metadata")
    assert response.status_code == 200

    data = response.json()
    assert data["tags"] == tags


def test_duplicate_tags_handling(client):
    """Test handling of duplicate tags."""
    project = "test_project"
    tags = ["test", "experiment", "test", "experiment"]  # Duplicates

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": tags})
    assert response.status_code == 200

    # Note: Backend may or may not remove duplicates automatically
    # This test documents the current behavior
    data = response.json()
    assert "tags" in data


def test_empty_tags_array(client):
    """Test updating with empty tags array."""
    project = "test_project"

    # Set initial tags
    client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": ["tag1", "tag2"]})

    # Clear tags
    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": []})
    assert response.status_code == 200

    data = response.json()
    assert data["tags"] == []


def test_tag_with_special_characters(client):
    """Test tags with special characters."""
    project = "test_project"
    tags = [
        "tag-with-dash",
        "tag_with_underscore",
        "tag.with.dot",
        "tag:with:colon",
        "tag/with/slash",
    ]

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": tags})
    assert response.status_code == 200

    data = response.json()
    assert "tags" in data


def test_tag_with_spaces(client):
    """Test tags with spaces."""
    project = "test_project"
    tags = ["tag with spaces", "another tag"]

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": tags})
    assert response.status_code == 200

    data = response.json()
    assert "tags" in data


def test_very_long_tag(client):
    """Test handling of very long tag."""
    project = "test_project"
    long_tag = "x" * 200  # Very long tag
    tags = [long_tag]

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": tags})
    # Backend should accept or reject based on validation rules
    # This test documents the current behavior
    assert response.status_code in [200, 422]


def test_many_tags(client):
    """Test handling of many tags."""
    project = "test_project"
    tags = [f"tag{i}" for i in range(100)]  # 100 tags

    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": tags})
    assert response.status_code == 200

    data = response.json()
    assert len(data["tags"]) == 100


def test_run_tags_update(client):
    """Test updating run tags."""
    project = "test_project"
    run = "test_run"
    tags = ["model-v1", "baseline"]

    response = client.put(f"/api/projects/{project}/runs/{run}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": tags})
    assert response.status_code == 200

    data = response.json()
    assert data["tags"] == tags

    # Verify retrieval
    response = client.get(f"/api/projects/{project}/runs/{run}/metadata")
    assert response.status_code == 200

    data = response.json()
    assert data["tags"] == tags


def test_tags_only_update(client):
    """Test updating only tags without affecting notes."""
    project = "test_project"

    # Set initial metadata
    client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"notes": "Initial note", "tags": ["tag1"]})

    # Update only tags
    response = client.put(f"/api/projects/{project}/metadata", headers={"X-Requested-With": "XMLHttpRequest"}, json={"tags": ["tag2", "tag3"]})
    assert response.status_code == 200

    data = response.json()
    assert data["notes"] == "Initial note"  # Should be preserved
    assert data["tags"] == ["tag2", "tag3"]
