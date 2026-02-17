"""
Unit tests for delete API endpoints.
"""

from unittest.mock import MagicMock

import pytest

from aspara.catalog.run_catalog import ProjectNotFoundError, RunNotFoundError
from aspara.dashboard.dependencies import get_project_catalog, get_run_catalog
from aspara.dashboard.main import app


@pytest.fixture
def mock_project_catalog():
    """Fixture to provide a mock ProjectCatalog with cleanup."""
    mock = MagicMock()
    app.dependency_overrides[get_project_catalog] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.fixture
def mock_run_catalog():
    """Fixture to provide a mock RunCatalog with cleanup."""
    mock = MagicMock()
    app.dependency_overrides[get_run_catalog] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


class TestDeleteProjectAPI:
    """Tests for project deletion API."""

    def test_delete_project_success(self, test_client, mock_project_catalog):
        """Test successful project deletion."""
        response = test_client.delete(
            "/api/projects/test_project",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 204
        mock_project_catalog.delete.assert_called_once_with("test_project")

    def test_delete_project_not_found(self, test_client, mock_project_catalog):
        """Test deletion of non-existent project."""
        mock_project_catalog.delete.side_effect = ProjectNotFoundError("Project 'nonexistent' does not exist")

        response = test_client.delete(
            "/api/projects/nonexistent",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "does not exist" in data["detail"]

    def test_delete_project_empty_name(self, test_client):
        """Test deletion with empty project name."""
        response = test_client.delete(
            "/api/projects/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 404  # FastAPI returns 404 for empty path parameter

    def test_delete_project_permission_error(self, test_client, mock_project_catalog):
        """Test deletion with permission error."""
        mock_project_catalog.delete.side_effect = PermissionError("Permission denied")

        response = test_client.delete(
            "/api/projects/test_project",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 403
        data = response.json()
        # Error message is sanitized for security
        assert data["detail"] == "Permission denied"

    def test_delete_project_unexpected_error(self, test_client, mock_project_catalog):
        """Test deletion with unexpected error."""
        mock_project_catalog.delete.side_effect = Exception("Unexpected error")

        response = test_client.delete(
            "/api/projects/test_project",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 500
        data = response.json()
        # Error message is sanitized for security (doesn't expose internal details)
        assert data["detail"] == "Failed to delete project"

    def test_delete_project_missing_csrf_header(self, test_client, mock_project_catalog):
        """Test deletion without CSRF header."""
        response = test_client.delete("/api/projects/test_project")

        assert response.status_code == 403
        data = response.json()
        assert "X-Requested-With" in data["detail"]


class TestDeleteRunAPI:
    """Tests for run deletion API."""

    def test_delete_run_success(self, test_client, mock_run_catalog):
        """Test successful run deletion."""
        response = test_client.delete(
            "/api/projects/test_project/runs/test_run",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 204
        mock_run_catalog.delete.assert_called_once_with("test_project", "test_run")

    def test_delete_run_project_not_found(self, test_client, mock_run_catalog):
        """Test deletion of run in non-existent project."""
        mock_run_catalog.delete.side_effect = ProjectNotFoundError("Project 'nonexistent' does not exist")

        response = test_client.delete(
            "/api/projects/nonexistent/runs/test_run",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "does not exist" in data["detail"]

    def test_delete_run_not_found(self, test_client, mock_run_catalog):
        """Test deletion of non-existent run."""
        mock_run_catalog.delete.side_effect = RunNotFoundError("Run 'nonexistent' does not exist in project 'test_project'")

        response = test_client.delete(
            "/api/projects/test_project/runs/nonexistent",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "does not exist" in data["detail"]

    def test_delete_run_empty_names(self, test_client):
        """Test deletion with empty names."""
        response = test_client.delete(
            "/api/projects/test_project/runs/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 404  # Empty run name results in 404

    def test_delete_run_permission_error(self, test_client, mock_run_catalog):
        """Test deletion with permission error."""
        mock_run_catalog.delete.side_effect = PermissionError("Permission denied")

        response = test_client.delete(
            "/api/projects/test_project/runs/test_run",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 403
        data = response.json()
        # Error message is sanitized for security
        assert data["detail"] == "Permission denied"


class TestDeleteAPISpecialCharacters:
    """Tests for delete APIs with special characters."""

    def test_delete_project_with_special_characters(self, test_client):
        """Test project deletion with special characters in name."""
        # Test with URL-encoded special characters (spaces are not allowed)
        response = test_client.delete(
            "/api/projects/test%20project",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        # Should return 400 because spaces are not allowed in project names
        assert response.status_code == 400
        data = response.json()
        assert "Invalid project name" in data["detail"]

    def test_delete_run_with_special_characters(self, test_client):
        """Test run deletion with special characters in name."""
        response = test_client.delete(
            "/api/projects/test%20project/runs/test%20run",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        # Should return 400 because spaces are not allowed in project/run names
        assert response.status_code == 400
        data = response.json()
        assert "Invalid project name" in data["detail"]


class TestDeleteAPIIntegration:
    """Integration tests that verify actual file deletion (no mocks).

    These tests use real filesystem operations to ensure that delete
    operations actually remove files and directories as expected.
    """

    def test_delete_project_removes_directory(self, test_client, tmp_path):
        """Test that deleting a project actually removes the directory."""
        from aspara.dashboard.router import configure_data_dir

        # Create test project with real files
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        (project_dir / "run_1.jsonl").write_text('{"type":"params"}\n')
        (project_dir / "run_2.jsonl").write_text('{"type":"params"}\n')

        # Initialize services with test directory
        configure_data_dir(data_dir=str(tmp_path))

        # Clear any previous dependency overrides
        app.dependency_overrides.clear()

        # Verify directory exists
        assert project_dir.exists()
        assert (project_dir / "run_1.jsonl").exists()

        # Delete project
        response = test_client.delete(
            "/api/projects/test_project",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        # Verify response
        assert response.status_code == 204

        # Verify directory was actually deleted
        assert not project_dir.exists()

    def test_delete_run_removes_file(self, test_client, tmp_path):
        """Test that deleting a run actually removes the file."""
        from aspara.dashboard.router import configure_data_dir

        # Create test project with run files
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run1_file = project_dir / "run_1.jsonl"
        run2_file = project_dir / "run_2.jsonl"
        run1_file.write_text('{"type":"params"}\n')
        run2_file.write_text('{"type":"params"}\n')

        # Initialize services with test directory
        configure_data_dir(data_dir=str(tmp_path))

        # Clear any previous dependency overrides
        app.dependency_overrides.clear()

        # Verify files exist
        assert run1_file.exists()
        assert run2_file.exists()

        # Delete one run
        response = test_client.delete(
            "/api/projects/test_project/runs/run_1",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        # Verify response
        assert response.status_code == 204

        # Verify only the specified file was deleted
        assert not run1_file.exists()
        assert run2_file.exists()  # Other run should still exist
        assert project_dir.exists()  # Project directory should still exist

    def test_delete_run_with_artifacts(self, test_client, tmp_path):
        """Test that deleting a run with artifacts removes both file and directory."""
        from aspara.dashboard.router import configure_data_dir

        # Create test project with run and artifacts
        # Directory structure: project/run.jsonl and project/run/artifacts/
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "test_run.jsonl"
        run_file.write_text('{"type":"params"}\n')

        # Create artifacts in the correct structure: run/artifacts/
        run_dir = project_dir / "test_run"
        run_dir.mkdir()
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "artifact1.txt").write_text("artifact data")
        (artifacts_dir / "artifact2.png").write_bytes(b"PNG data")

        # Initialize services with test directory
        configure_data_dir(data_dir=str(tmp_path))

        # Clear any previous dependency overrides
        app.dependency_overrides.clear()

        # Verify files exist
        assert run_file.exists()
        assert artifacts_dir.exists()
        assert (artifacts_dir / "artifact1.txt").exists()

        # Delete run
        response = test_client.delete(
            "/api/projects/test_project/runs/test_run",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        # Verify response
        assert response.status_code == 204

        # Verify file, artifacts directory, and run directory were deleted
        assert not run_file.exists()
        assert not artifacts_dir.exists()
        assert not run_dir.exists()  # run directory should also be removed
