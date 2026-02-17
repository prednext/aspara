"""
Integration tests for Polars backend with aspara.run module.

Tests the complete workflow:
- aspara.init(storage_backend="polars")
- Logging metrics
- Reading metrics back
- Catalog discovery
"""

import tempfile
from pathlib import Path

import pytest

import aspara


class TestPolarsBackendIntegration:
    """Test Polars backend end-to-end integration."""

    def test_init_with_polars_backend(self):
        """Test that aspara.init() with storage_backend='polars' creates a working run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run = aspara.init(
                project="test_project",
                name="polars_run",
                storage_backend="polars",
                dir=tmpdir,
            )

            # Verify the run was created
            assert run is not None
            assert run.name == "polars_run"
            assert run.project == "test_project"
            assert run.backend._storage_backend_type == "polars"

            # Verify PolarsMetricsStorage was used
            from aspara.storage.metrics import PolarsMetricsStorage

            assert isinstance(run.backend._metrics_storage, PolarsMetricsStorage)

            aspara.finish()

    def test_log_and_read_metrics_with_polars(self):
        """Test logging metrics with Polars backend and reading them back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize run with Polars backend
            run = aspara.init(
                project="test_project",
                name="polars_run",
                storage_backend="polars",
                dir=tmpdir,
            )

            # Log some metrics
            run.log({"loss": 0.5, "accuracy": 0.95}, step=0)
            run.log({"loss": 0.3, "accuracy": 0.97}, step=1)
            run.log({"loss": 0.1, "accuracy": 0.99}, step=2)

            aspara.finish()

            # Verify WAL file was created
            wal_file = Path(tmpdir) / "test_project" / "polars_run.wal.jsonl"
            assert wal_file.exists(), "WAL file should be created"

            # Read metrics back using PolarsMetricsStorage
            from aspara.storage.metrics import PolarsMetricsStorage

            storage = PolarsMetricsStorage(
                base_dir=tmpdir,
                project_name="test_project",
                run_name="polars_run",
            )

            result = storage.load()
            import polars as pl

            # Verify metrics were saved correctly - DataFrame format
            assert isinstance(result, pl.DataFrame)
            assert len(result) == 3, "Should have 3 metric records"
            assert "_loss" in result.columns
            assert "_accuracy" in result.columns

            assert result.filter(pl.col("step") == 0).select("_loss").item() == 0.5
            assert result.filter(pl.col("step") == 0).select("_accuracy").item() == 0.95

            assert result.filter(pl.col("step") == 1).select("_loss").item() == 0.3
            assert result.filter(pl.col("step") == 1).select("_accuracy").item() == 0.97

            assert result.filter(pl.col("step") == 2).select("_loss").item() == 0.1
            assert result.filter(pl.col("step") == 2).select("_accuracy").item() == 0.99

    def test_polars_run_discovered_by_catalog(self):
        """Test that Polars-backed runs are discovered by RunCatalog."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a run with Polars backend
            run = aspara.init(
                project="test_project",
                name="polars_run",
                storage_backend="polars",
                dir=tmpdir,
            )

            run.log({"loss": 0.5}, step=0)
            aspara.finish()

            # Use RunCatalog to discover runs
            from aspara.catalog import RunCatalog

            catalog = RunCatalog(data_dir=tmpdir)
            runs = catalog.get_runs(project="test_project")

            # Verify the Polars run was discovered
            assert len(runs) == 1, "Should discover 1 run"
            assert runs[0].name == "polars_run"
            assert runs[0].is_finished is True

    def test_polars_archive_threshold(self):
        """Test that Polars backend archives to Parquet when WAL exceeds threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a small threshold to trigger archiving (10KB)
            from aspara.storage import PolarsMetricsStorage

            storage = PolarsMetricsStorage(
                base_dir=tmpdir,
                project_name="test_project",
                run_name="archive_test",
                archive_threshold_bytes=10 * 1024,  # 10KB threshold
            )

            # Write enough metrics to exceed threshold
            for i in range(1000):
                # Calculate hours and minutes from counter
                hours = i // 60
                minutes = i % 60
                seconds = 0
                storage.save({
                    "timestamp": f"2024-01-01T{hours:02d}:{minutes:02d}:{seconds:02d}",
                    "step": i,
                    "metrics": {
                        "loss": 1.0 - i * 0.001,
                        "accuracy": 0.5 + i * 0.0005,
                        "f1_score": 0.6 + i * 0.0004,
                    },
                })

            # Verify archive was created
            archive_path = Path(tmpdir) / "test_project" / "archive_test_archive"
            assert archive_path.exists(), "Archive directory should be created"

            # Verify Parquet files exist
            parquet_files = list(archive_path.rglob("*.parquet"))
            assert len(parquet_files) > 0, "Should have Parquet files in archive"

            # Verify WAL was cleared
            wal_file = Path(tmpdir) / "test_project" / "archive_test.wal.jsonl"
            if wal_file.exists():
                wal_size = wal_file.stat().st_size
                assert wal_size < 10 * 1024, "WAL should be smaller than threshold after archiving"

    def test_mixed_wal_and_parquet_reading(self):
        """Test reading metrics from both WAL and Parquet archives."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from aspara.storage import PolarsMetricsStorage

            storage = PolarsMetricsStorage(
                base_dir=tmpdir,
                project_name="test_project",
                run_name="mixed_test",
                archive_threshold_bytes=1 * 1024,  # 1KB threshold for quick archiving
            )

            # Write metrics that will be archived
            for i in range(100):
                minutes = i % 60
                hours = i // 60
                storage.save({
                    "timestamp": f"2024-01-01T{hours:02d}:{minutes:02d}:00",
                    "step": i,
                    "metrics": {"loss": 1.0 - i * 0.01},
                })

            # Write a few more metrics that stay in WAL
            for i in range(100, 103):
                minutes = i % 60
                hours = i // 60
                storage.save({
                    "timestamp": f"2024-01-01T{hours:02d}:{minutes:02d}:00",
                    "step": i,
                    "metrics": {"loss": 1.0 - i * 0.01},
                })

            # Read all metrics
            result = storage.load()
            import polars as pl

            # Should get all metrics (archived + WAL) - DataFrame format
            assert isinstance(result, pl.DataFrame)
            assert len(result) >= 103, "Should read from both Parquet archive and WAL"

            # Verify metrics are sorted by timestamp
            timestamps = result.select("timestamp").to_series().to_list()
            assert timestamps == sorted(timestamps), "Metrics should be sorted by timestamp"

    def test_polars_backend_with_config_and_summary(self):
        """Test Polars backend with config and summary (stored in metadata)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run = aspara.init(
                project="test_project",
                name="polars_run",
                config={"learning_rate": 0.001, "batch_size": 32},
                tags=["experiment", "polars"],
                storage_backend="polars",
                dir=tmpdir,
            )

            run.log({"loss": 0.5}, step=0)

            run.summary["best_loss"] = 0.1
            run.summary["best_accuracy"] = 0.99

            aspara.finish()

            # Verify metadata file was created
            metadata_file = Path(tmpdir) / "test_project" / "polars_run.meta.json"
            assert metadata_file.exists(), "Metadata file should be created"

            # Read metadata
            import json

            with open(metadata_file) as f:
                metadata = json.load(f)

            assert metadata["config"]["learning_rate"] == 0.001
            assert metadata["config"]["batch_size"] == 32
            assert metadata["tags"] == ["experiment", "polars"]
            assert metadata["summary"]["best_loss"] == 0.1
            assert metadata["summary"]["best_accuracy"] == 0.99

    def test_finish_flushes_wal_to_parquet(self):
        """Test that aspara.finish() flushes WAL to Parquet archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize run with Polars backend
            aspara.init(
                project="test_project",
                name="finish_test",
                storage_backend="polars",
                dir=tmpdir,
            )

            # Log some metrics (will go to WAL)
            aspara.log({"loss": 0.5, "accuracy": 0.95}, step=0)
            aspara.log({"loss": 0.3, "accuracy": 0.97}, step=1)

            # Verify WAL exists before finish
            wal_file = Path(tmpdir) / "test_project" / "finish_test.wal.jsonl"
            assert wal_file.exists(), "WAL file should exist before finish"
            assert wal_file.stat().st_size > 0, "WAL should have data before finish"

            # Call finish (should flush WAL to Parquet)
            aspara.finish()

            # Verify archive was created
            archive_path = Path(tmpdir) / "test_project" / "finish_test_archive"
            assert archive_path.exists(), "Archive directory should be created after finish"

            # Verify Parquet files exist
            parquet_files = list(archive_path.rglob("*.parquet"))
            assert len(parquet_files) > 0, "Should have Parquet files in archive after finish"

            # Verify WAL was cleared
            if wal_file.exists():
                wal_size = wal_file.stat().st_size
                assert wal_size == 0, "WAL should be empty after finish"

            # Verify we can still read the metrics from Parquet
            from aspara.storage.metrics import PolarsMetricsStorage

            storage = PolarsMetricsStorage(
                base_dir=tmpdir,
                project_name="test_project",
                run_name="finish_test",
            )

            result = storage.load()
            import polars as pl

            # DataFrame format
            assert isinstance(result, pl.DataFrame)
            assert len(result) == 2, "Should read 2 metrics from Parquet archive"
            assert result.filter(pl.col("step") == 0).select("_loss").item() == 0.5
            assert result.filter(pl.col("step") == 1).select("_loss").item() == 0.3


class TestPolarsBackendErrors:
    """Test error handling for Polars backend."""

    def test_polars_backend_fallback_to_jsonl(self):
        """Test that invalid backend falls back to JSONL gracefully."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ValueError),
        ):
            # Test with an invalid backend name
            # This should now be treated as a configuration error
            aspara.init(
                project="test_project",
                name="fallback_run",
                storage_backend="invalid_backend",  # Invalid backend
                dir=tmpdir,
            )

    def test_read_nonexistent_polars_run(self):
        """Test reading from a nonexistent Polars run raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from aspara.exceptions import RunNotFoundError
            from aspara.storage.metrics import PolarsMetricsStorage

            storage = PolarsMetricsStorage(
                base_dir=tmpdir,
                project_name="test_project",
                run_name="nonexistent_run",
            )

            with pytest.raises(RunNotFoundError):
                storage.load()
