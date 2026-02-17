"""
Test 404 error handling for non-existent projects and runs.

NOTE: This test file no longer uses unittest.mock.patch - it uses
dependency injection via configure_data_dir() to set up real
MetricsReader instances with test data directories.
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory with test project structure."""
    temp_dir = tempfile.mkdtemp()
    data_path = Path(temp_dir)

    # Create test_project
    project_dir = data_path / "test_project"
    project_dir.mkdir(parents=True)

    # Create a test run file
    run_file = project_dir / "run_1.jsonl"
    run_file.write_text('{"type": "params", "timestamp": "2024-01-15T10:00:00", "run": "run_1", "project": "test_project", "params": {"lr": 0.01}}\n')

    yield data_path

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)


class TestNotFoundHandling:
    """Test proper 404 error responses for non-existent resources."""

    def test_nonexistent_project_returns_404(self, test_client, temp_data_dir):
        """Test that accessing a non-existent project returns 404."""
        from aspara.dashboard.router import configure_data_dir

        # Initialize services with test data directory (no mocks!)
        configure_data_dir(data_dir=str(temp_data_dir))

        response = test_client.get("/projects/nonexistent_project")
        assert response.status_code == 404
        assert "Project 'nonexistent_project' not found" in response.json()["detail"]

    def test_nonexistent_run_returns_404(self, test_client, temp_data_dir):
        """Test that accessing a non-existent run returns 404."""
        from aspara.dashboard.router import configure_data_dir

        # Initialize services with test data directory (no mocks!)
        configure_data_dir(data_dir=str(temp_data_dir))

        response = test_client.get("/projects/test_project/runs/nonexistent_run")
        assert response.status_code == 404
        assert "Run 'nonexistent_run' not found" in response.json()["detail"]

    def test_nonexistent_project_run_returns_404(self, test_client, temp_data_dir):
        """Test that accessing a run in a non-existent project returns 404."""
        from aspara.dashboard.router import configure_data_dir

        # Initialize services with test data directory (no mocks!)
        configure_data_dir(data_dir=str(temp_data_dir))

        response = test_client.get("/projects/nonexistent_project/runs/some_run")
        assert response.status_code == 404
        assert "Project 'nonexistent_project' not found" in response.json()["detail"]
