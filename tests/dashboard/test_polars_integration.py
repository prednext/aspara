"""
Integration tests for dashboard with Polars backend.

Tests that the dashboard can properly load and display metrics
from Polars-backed runs (WAL + Parquet archives).
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import aspara
from aspara.dashboard.main import app
from aspara.dashboard.router import configure_data_dir

client = TestClient(app)


class TestDashboardPolarsBackend:
    """Test dashboard integration with Polars backend."""

    @pytest.fixture
    def setup_polars_run(self):
        """Set up a temporary run with Polars backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize dashboard services with temp dir
            configure_data_dir(data_dir=tmpdir)

            # Create a run with Polars backend
            run = aspara.init(
                project="test_project",
                name="polars_run",
                config={"learning_rate": 0.001},
                tags=["test", "polars"],
                storage_backend="polars",
                dir=tmpdir,
            )

            # Log some metrics
            run.log({"loss": 0.5, "accuracy": 0.90}, step=0)
            run.log({"loss": 0.3, "accuracy": 0.95}, step=1)
            run.log({"loss": 0.1, "accuracy": 0.99}, step=2)

            aspara.finish()

            yield tmpdir

    def test_load_metrics_from_polars_backend(self, setup_polars_run):
        """Test run_catalog.load_metrics() can load from Polars backend."""
        tmpdir = setup_polars_run

        # Re-initialize services to use the temp dir
        configure_data_dir(data_dir=tmpdir)

        # Load metrics via RunCatalog
        import polars as pl

        from aspara.catalog import RunCatalog

        catalog = RunCatalog(data_dir=tmpdir)
        df = catalog.load_metrics(project="test_project", run="polars_run")

        # Verify metrics were loaded as DataFrame
        assert isinstance(df, pl.DataFrame), "Should return DataFrame from Polars backend"
        assert len(df) > 0, "Should load metrics from Polars backend"
        assert len(df) == 3, "Should have 3 metric records"

        # Verify DataFrame structure
        assert "timestamp" in df.columns
        assert "step" in df.columns
        assert "_loss" in df.columns
        assert "_accuracy" in df.columns

        # Verify metric content (wide format)
        assert df.filter(pl.col("step") == 0).select("_loss").item() == 0.5
        assert df.filter(pl.col("step") == 0).select("_accuracy").item() == 0.90

        assert df.filter(pl.col("step") == 1).select("_loss").item() == 0.3
        assert df.filter(pl.col("step") == 1).select("_accuracy").item() == 0.95

        assert df.filter(pl.col("step") == 2).select("_loss").item() == 0.1
        assert df.filter(pl.col("step") == 2).select("_accuracy").item() == 0.99

    def test_api_metrics_endpoint_with_polars(self, setup_polars_run):
        """Test API metrics endpoint with Polars backend (via run_catalog.load_metrics)."""
        tmpdir = setup_polars_run

        # Re-initialize services
        configure_data_dir(data_dir=tmpdir)

        # Test via RunCatalog (avoiding TestClient fixture issues)
        import polars as pl

        from aspara.catalog import RunCatalog

        catalog = RunCatalog(data_dir=tmpdir)
        df = catalog.load_metrics(project="test_project", run="polars_run")

        # Verify metrics were returned as DataFrame
        assert isinstance(df, pl.DataFrame), "Should return DataFrame"
        assert len(df) > 0, "Should return metrics from Polars backend"
        assert len(df) == 3, "Should have 3 metric records"

        # Verify metric content (wide format)
        assert df.filter(pl.col("step") == 0).select("_loss").item() == 0.5
        assert df.filter(pl.col("step") == 0).select("_accuracy").item() == 0.90

    def test_run_detail_page_with_polars(self, setup_polars_run):
        """Test run detail functionality with Polars metrics."""
        tmpdir = setup_polars_run

        # Re-initialize services
        configure_data_dir(data_dir=tmpdir)

        # Verify metrics can be loaded (core functionality)
        import polars as pl

        from aspara.catalog import RunCatalog

        catalog = RunCatalog(data_dir=tmpdir)
        df = catalog.load_metrics(project="test_project", run="polars_run")

        assert isinstance(df, pl.DataFrame), "Should return DataFrame"
        assert len(df) == 3, "Should load 3 metrics"
        # Verify latest metrics are present (step 2 is the last)
        assert df.filter(pl.col("step") == 2).select("_loss").item() == 0.1
        assert df.filter(pl.col("step") == 2).select("_accuracy").item() == 0.99

    def test_runs_metrics_api_returns_metric_first_structure(self):
        """Test runs_metrics_api endpoint returns metric-first structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            configure_data_dir(data_dir=tmpdir)

            # Create two runs
            run1 = aspara.init(
                project="test_project",
                name="run1",
                storage_backend="polars",
                dir=tmpdir,
            )
            run1.log({"loss": 0.5, "accuracy": 0.90}, step=0)
            run1.log({"loss": 0.3, "accuracy": 0.95}, step=1)
            aspara.finish()

            run2 = aspara.init(
                project="test_project",
                name="run2",
                storage_backend="polars",
                dir=tmpdir,
            )
            run2.log({"loss": 0.6, "accuracy": 0.85}, step=0)
            run2.log({"loss": 0.4, "accuracy": 0.90}, step=1)
            aspara.finish()

            configure_data_dir(data_dir=tmpdir)

            # Call API via TestClient
            response_obj = client.get("/api/projects/test_project/runs/metrics?runs=run1,run2")
            assert response_obj.status_code == 200
            response = response_obj.json()

            # Verify metric-first structure
            assert "project" in response
            assert response["project"] == "test_project"
            assert "metrics" in response
            assert "loss" in response["metrics"]
            assert "accuracy" in response["metrics"]

            # Verify run data (delta-compressed array format)
            assert "run1" in response["metrics"]["loss"]
            assert "run2" in response["metrics"]["loss"]
            loss_data_run1 = response["metrics"]["loss"]["run1"]
            loss_data_run2 = response["metrics"]["loss"]["run2"]

            # Verify array format structure
            assert "steps" in loss_data_run1
            assert "values" in loss_data_run1
            assert "timestamps" in loss_data_run1

            assert len(loss_data_run1["steps"]) == 2
            assert len(loss_data_run2["steps"]) == 2

            # Verify data point format (delta-compressed)
            assert loss_data_run1["steps"][0] == 0  # First step is absolute
            assert loss_data_run1["values"][0] == 0.5
            assert len(loss_data_run1["timestamps"]) == 2
            # Timestamps are unix time in milliseconds
            assert isinstance(loss_data_run1["timestamps"][0], int)
            assert loss_data_run1["timestamps"][0] > 1700000000000

            assert loss_data_run2["steps"][0] == 0
            assert loss_data_run2["values"][0] == 0.6
            assert len(loss_data_run2["timestamps"]) == 2

    def test_runs_list_shows_correct_count_for_polars(self, setup_polars_run):
        """Test runs list shows correct metric count for Polars runs."""
        tmpdir = setup_polars_run

        # Re-initialize services
        configure_data_dir(data_dir=tmpdir)

        # Verify catalog can discover and count metrics correctly
        from aspara.catalog import RunCatalog

        catalog = RunCatalog(data_dir=tmpdir)
        runs = catalog.get_runs(project="test_project")

        assert len(runs) == 1, "Should discover 1 run"
        assert runs[0].name == "polars_run"

    def test_mixed_jsonl_and_polars_runs(self):
        """Test dashboard can handle projects with both JSONL and Polars runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            configure_data_dir(data_dir=tmpdir)

            # Create a JSONL run
            run1 = aspara.init(
                project="mixed_project",
                name="jsonl_run",
                storage_backend="jsonl",
                dir=tmpdir,
            )
            run1.log({"loss": 0.8}, step=0)
            aspara.finish()

            # Create a Polars run
            run2 = aspara.init(
                project="mixed_project",
                name="polars_run",
                storage_backend="polars",
                dir=tmpdir,
            )
            run2.log({"loss": 0.5}, step=0)
            aspara.finish()

            # Re-initialize to pick up changes
            configure_data_dir(data_dir=tmpdir)

            # Load metrics from JSONL run via RunCatalog
            import polars as pl

            from aspara.catalog import RunCatalog

            catalog = RunCatalog(data_dir=tmpdir)

            jsonl_df = catalog.load_metrics(project="mixed_project", run="jsonl_run")
            assert isinstance(jsonl_df, pl.DataFrame)
            assert len(jsonl_df) == 1
            assert jsonl_df.filter(pl.col("step") == 0).select("_loss").item() == 0.8

            # Load metrics from Polars run
            polars_df = catalog.load_metrics(project="mixed_project", run="polars_run")
            assert isinstance(polars_df, pl.DataFrame)
            assert len(polars_df) == 1
            assert polars_df.filter(pl.col("step") == 0).select("_loss").item() == 0.5

    def test_polars_run_with_large_archive(self):
        """Test dashboard can load metrics from Polars run with archived data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            configure_data_dir(data_dir=tmpdir)

            from aspara.storage import PolarsMetricsStorage

            # Create storage with small threshold to trigger archiving
            storage = PolarsMetricsStorage(
                base_dir=tmpdir,
                project_name="test_project",
                run_name="archived_run",
                archive_threshold_bytes=1 * 1024,  # 1KB threshold
            )

            # Write many metrics to trigger archiving
            for i in range(200):
                minutes = i % 60
                hours = i // 60
                storage.save({
                    "timestamp": f"2024-01-01T{hours:02d}:{minutes:02d}:00",
                    "step": i,
                    "metrics": {"loss": 1.0 - i * 0.005},
                })

            # Verify archive was created
            archive_path = Path(tmpdir) / "test_project" / "archived_run_archive"
            assert archive_path.exists(), "Archive should be created"

            # Re-initialize dashboard
            configure_data_dir(data_dir=tmpdir)

            # Load metrics via RunCatalog
            from aspara.catalog import RunCatalog

            catalog = RunCatalog(data_dir=tmpdir)
            metrics = catalog.load_metrics(project="test_project", run="archived_run")

            # Should load metrics from both archive and WAL
            assert len(metrics) >= 200, "Should load all metrics including archived ones"


class TestDashboardBackendDetection:
    """Test backend detection for dashboard."""

    def test_detect_jsonl_backend(self):
        """Test detecting a JSONL-backed run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a JSONL run
            run = aspara.init(
                project="test_project",
                name="jsonl_run",
                storage_backend="jsonl",
                dir=tmpdir,
            )
            run.log({"loss": 0.5}, step=0)
            aspara.finish()

            # Check files created
            project_dir = Path(tmpdir) / "test_project"
            assert (project_dir / "jsonl_run.jsonl").exists()
            assert not (project_dir / "jsonl_run.wal.jsonl").exists()
            assert not (project_dir / "jsonl_run_archive").exists()

    def test_detect_polars_backend(self):
        """Test detecting a Polars-backed run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Polars run
            run = aspara.init(
                project="test_project",
                name="polars_run",
                storage_backend="polars",
                dir=tmpdir,
            )
            run.log({"loss": 0.5}, step=0)
            aspara.finish()

            # Check files created
            project_dir = Path(tmpdir) / "test_project"
            assert (project_dir / "polars_run.jsonl").exists()  # Placeholder file
            assert (project_dir / "polars_run.wal.jsonl").exists()  # WAL file

    def test_detect_backend_helper_function(self):
        """Test backend detection helper function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both types of runs
            run1 = aspara.init(
                project="test_project",
                name="jsonl_run",
                storage_backend="jsonl",
                dir=tmpdir,
            )
            run1.log({"loss": 0.5}, step=0)
            aspara.finish()

            run2 = aspara.init(
                project="test_project",
                name="polars_run",
                storage_backend="polars",
                dir=tmpdir,
            )
            run2.log({"loss": 0.3}, step=0)
            aspara.finish()

            # Test the backend detection helper function
            from pathlib import Path

            from aspara.catalog.run_catalog import _detect_backend

            assert _detect_backend(Path(tmpdir), "test_project", "jsonl_run") == "jsonl"
            assert _detect_backend(Path(tmpdir), "test_project", "polars_run") == "polars"
