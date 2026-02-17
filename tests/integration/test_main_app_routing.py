"""
Integration test for the main aspara application routing.
This tests the actual app that gets deployed, not just the dashboard module.

Updated for refactored APIRouter-based architecture using Catalog classes.

Note: The main app mounts the dashboard app as a sub-application.
Dependency overrides must be set on the dashboard app, not the main app.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import polars as pl
from starlette.testclient import TestClient

from aspara.catalog.run_catalog import RunInfo
from aspara.dashboard.dependencies import get_data_dir_path, get_project_catalog, get_run_catalog
from aspara.dashboard.main import app as dashboard_app
from aspara.server import app


class TestMainAppProjectRouting:
    """Test that the main aspara app correctly routes to project pages."""

    def test_main_app_run_detail_routing(self):
        """Test that run detail routing works correctly in main app."""
        mock_run = RunInfo(
            name="run_1",
            run_id=None,
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            last_update=datetime(2024, 1, 15, 10, 30, 0),
            param_count=3,
            artifact_count=0,
            tags=[],
            is_corrupted=False,
            error_message=None,
            is_finished=False,
            exit_code=None,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            mock_logs_dir = Path(temp_dir)
            project_dir = mock_logs_dir / "test_project"
            project_dir.mkdir(exist_ok=True)
            run_file = project_dir / "run_1.jsonl"
            run_file.touch()

            # Create mock catalogs
            mock_project_catalog = MagicMock()
            mock_project_catalog.exists.return_value = True

            mock_run_catalog = MagicMock()
            mock_run_catalog.get.return_value = mock_run
            mock_run_catalog.get_artifacts.return_value = []
            mock_run_catalog.get_artifacts_async = AsyncMock(return_value=[])
            mock_run_catalog.get_run_config_async = AsyncMock(return_value={})
            mock_run_catalog.load_metrics.return_value = pl.DataFrame({
                "timestamp": [],
                "step": [],
            })

            # Override dependencies on the dashboard app (mounted sub-application)
            dashboard_app.dependency_overrides[get_project_catalog] = lambda: mock_project_catalog
            dashboard_app.dependency_overrides[get_run_catalog] = lambda: mock_run_catalog
            dashboard_app.dependency_overrides[get_data_dir_path] = lambda: mock_logs_dir

            try:
                client = TestClient(app)
                response = client.get("/projects/test_project/runs/run_1")

                assert response.status_code == 200
                content = response.text
                assert "run_1" in content
            finally:
                dashboard_app.dependency_overrides.clear()

    def test_main_app_runs_list_routing(self):
        """Test that runs list routing works correctly in main app."""
        mock_runs = [
            RunInfo(
                name="test_run",
                run_id=None,
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                last_update=datetime(2024, 1, 15, 10, 30, 0),
                param_count=3,
                artifact_count=0,
                tags=[],
                is_corrupted=False,
                error_message=None,
                is_finished=False,
                exit_code=None,
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            mock_logs_dir = Path(temp_dir)
            project_dir = mock_logs_dir / "test_project"
            project_dir.mkdir(exist_ok=True)

            # Create mock catalogs
            mock_project_catalog = MagicMock()
            mock_project_catalog.exists.return_value = True

            mock_run_catalog = MagicMock()
            mock_run_catalog.get_runs.return_value = mock_runs

            # Override dependencies on the dashboard app
            dashboard_app.dependency_overrides[get_project_catalog] = lambda: mock_project_catalog
            dashboard_app.dependency_overrides[get_run_catalog] = lambda: mock_run_catalog
            dashboard_app.dependency_overrides[get_data_dir_path] = lambda: mock_logs_dir

            try:
                client = TestClient(app)
                response = client.get("/projects/test_project")

                assert response.status_code == 200
                content = response.text
                # Check that runs page content is shown (project detail page)
                assert "test_project" in content
            finally:
                dashboard_app.dependency_overrides.clear()


class TestMainAppAPIRouting:
    """Test API routing in the main app."""

    def test_main_app_compare_runs_api(self):
        """Test compare runs API routing in main app."""
        # Create mock catalog
        mock_run_catalog = MagicMock()
        mock_run_catalog.load_metrics.return_value = pl.DataFrame({
            "timestamp": [],
            "step": [],
        })

        # Override dependencies on the dashboard app
        dashboard_app.dependency_overrides[get_run_catalog] = lambda: mock_run_catalog

        try:
            client = TestClient(app)
            response = client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2")

            # Should route to the correct API endpoint
            assert response.status_code == 200
            data = response.json()
            assert "project" in data
            assert "metrics" in data
            assert data["project"] == "test_project"
        finally:
            dashboard_app.dependency_overrides.clear()
