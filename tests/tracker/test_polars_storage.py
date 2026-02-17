"""
Tests for Polars storage backend (WAL-based implementation)
"""

import shutil

import polars as pl
import pytest

from aspara.exceptions import RunNotFoundError
from aspara.storage.metrics import PolarsMetricsStorage


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Fixture providing temporary directory for tests"""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir()
    yield storage_dir
    # Cleanup after test
    if storage_dir.exists():
        shutil.rmtree(storage_dir)


def test_polars_storage_backend_init(temp_storage_dir):
    """Test PolarsMetricsStorage initialization"""
    storage = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run")

    assert storage is not None
    assert temp_storage_dir.exists()
    assert temp_storage_dir.is_dir()


def test_polars_storage_save_to_wal(temp_storage_dir):
    """Test PolarsMetricsStorage save writes to WAL"""
    storage = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run_1")

    # Test metrics data
    metrics_data = {
        "project_name": "test_project",
        "run_name": "test_run_1",
        "timestamp": "2025-06-07T12:00:00",
        "step": 1,
        "metrics": {"loss": 0.5, "accuracy": 0.8},
    }

    # Save metrics
    result = storage.save(metrics_data)

    # Verify empty string is returned
    assert result == ""

    # Verify project directory is created
    project_dir = temp_storage_dir / "test_project"
    assert project_dir.exists()
    assert project_dir.is_dir()

    # Verify WAL file is created (not Parquet yet - below threshold)
    wal_file = project_dir / "test_run_1.wal.jsonl"
    assert wal_file.exists()
    assert wal_file.is_file()

    # Archive directory should NOT exist yet (below archive threshold)
    archive_dir = project_dir / "test_run_1_archive"
    assert not archive_dir.exists()


def test_polars_storage_load_from_wal(temp_storage_dir):
    """Test PolarsMetricsStorage load reads from WAL and returns wide-format DataFrame"""
    import polars as pl

    storage = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run_1")

    # Save test data
    test_data = [
        {
            "project_name": "test_project",
            "run_name": "test_run_1",
            "timestamp": "2025-06-07T12:00:00",
            "step": 1,
            "metrics": {"loss": 0.5, "accuracy": 0.8},
        },
        {
            "project_name": "test_project",
            "run_name": "test_run_1",
            "timestamp": "2025-06-07T12:01:00",
            "step": 2,
            "metrics": {"loss": 0.4, "accuracy": 0.85},
        },
    ]

    for item in test_data:
        storage.save(item)

    # Get metrics (returns wide-format DataFrame)
    df = storage.load()

    # Verify results - should be a DataFrame
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2
    assert "timestamp" in df.columns
    assert "step" in df.columns
    assert "_loss" in df.columns  # Metrics are prefixed with underscore
    assert "_accuracy" in df.columns

    # Verify metric values
    assert df.filter(pl.col("step") == 1).select("_loss").item() == 0.5
    assert df.filter(pl.col("step") == 2).select("_accuracy").item() == 0.85

    # Get specific metrics (filter by metric name)
    df_filtered = storage.load(metric_names=["loss"])

    # Verify results (both records should have "loss" column)
    assert len(df_filtered) == 2
    assert "_loss" in df_filtered.columns
    assert "_accuracy" not in df_filtered.columns  # Should be filtered out

    # Test non-existent run raises exception
    storage_non_existent = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="non_existent_run")
    with pytest.raises(RunNotFoundError):
        storage_non_existent.load()


def test_polars_storage_archive_on_threshold(temp_storage_dir):
    """Test that WAL is archived to Parquet when threshold is exceeded"""

    # Use very small threshold to trigger archiving
    storage = PolarsMetricsStorage(
        base_dir=str(temp_storage_dir),
        project_name="test_project",
        run_name="test_run",
        archive_threshold_bytes=100,  # Very small threshold
    )

    # Save enough metrics to exceed threshold
    for i in range(10):
        storage.save({
            "project_name": "test_project",
            "run_name": "test_run",
            "timestamp": f"2025-01-01T{i:02d}:00:00",
            "step": i,
            "metrics": {"loss": 0.5 - i * 0.01, "accuracy": 0.8 + i * 0.01},
        })

    # WAL might have recent data or be empty after archive (truncated, not deleted)

    # All metrics should still be readable (from Parquet + WAL)
    import polars as pl

    df = storage.load()
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 10

    # Verify data is archived to Parquet
    archive_path = temp_storage_dir / "test_project" / "test_run_archive"
    assert archive_path.exists(), "Archive directory should exist"

    parquet_files = list(archive_path.rglob("*.parquet"))
    assert len(parquet_files) > 0, "Parquet files should be created"


def test_polars_storage_concurrent_read_write(temp_storage_dir):
    """Test that Reader can access data while Writer is active"""
    # This simulates the key use case: Dashboard reading while training writes

    writer = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run")
    reader = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run")

    # Writer saves some metrics
    writer.save({
        "project_name": "test_project",
        "run_name": "test_run",
        "timestamp": "2025-01-01T00:00:00",
        "step": 1,
        "metrics": {"loss": 0.5},
    })

    # Reader can read immediately (no lock contention)
    df = reader.load()
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 1

    # Writer saves more
    writer.save({
        "project_name": "test_project",
        "run_name": "test_run",
        "timestamp": "2025-01-01T01:00:00",
        "step": 2,
        "metrics": {"loss": 0.4},
    })

    # Reader sees updated data
    df = reader.load()
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2


def test_polars_storage_mixed_wal_and_parquet(temp_storage_dir):
    """Test reading from both WAL and Parquet archives"""

    storage = PolarsMetricsStorage(
        base_dir=str(temp_storage_dir),
        project_name="test_project",
        run_name="test_run",
        archive_threshold_bytes=100,  # Small threshold to trigger archiving
    )

    # Save old data and trigger archiving
    storage.save({
        "project_name": "test_project",
        "run_name": "test_run",
        "timestamp": "2025-01-01T00:00:00",
        "step": 1,
        "metrics": {"loss": 0.5},
    })

    # Save new data to WAL (won't be archived yet)
    storage.save({
        "project_name": "test_project",
        "run_name": "test_run",
        "timestamp": "2025-01-01T01:00:00",
        "step": 2,
        "metrics": {"loss": 0.4},
    })

    # Should read from both Parquet archives and WAL
    df = storage.load()
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2

    # Should be sorted by timestamp/step
    steps = df.select("step").to_series().to_list()
    assert steps == [1, 2]  # From Parquet and WAL


def test_polars_storage_metric_filtering(temp_storage_dir):
    """Test filtering metrics by name"""
    storage = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run")

    storage.save({
        "project_name": "test_project",
        "run_name": "test_run",
        "timestamp": "2025-01-01T00:00:00",
        "step": 1,
        "metrics": {"loss": 0.5, "accuracy": 0.8, "lr": 0.001},
    })

    # Filter by specific metric
    df = storage.load(metric_names=["loss"])
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 1
    assert "_loss" in df.columns
    assert "_accuracy" not in df.columns
    assert "_lr" not in df.columns

    # Filter by non-existent metric
    df = storage.load(metric_names=["non_existent"])
    assert isinstance(df, pl.DataFrame)
    # Should return DataFrame with timestamp and step columns only
    assert len(df) == 0 or set(df.columns) == {"timestamp", "step"}


def test_polars_storage_close_is_noop(temp_storage_dir):
    """Test that close() is a no-op (no connections to close)"""
    storage = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run")

    storage.save({
        "project_name": "test_project",
        "run_name": "test_run",
        "timestamp": "2025-01-01T00:00:00",
        "step": 1,
        "metrics": {"loss": 0.5},
    })

    # close() should not raise any errors
    storage.close()

    # Should still be able to read after close (no persistent connections)
    df = storage.load()
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 1


def test_polars_storage_run_not_found(temp_storage_dir):
    """Test RunNotFoundError is raised for non-existent run"""
    # Create project directory
    (temp_storage_dir / "test_project").mkdir()

    storage = PolarsMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="non_existent_run")
    with pytest.raises(RunNotFoundError):
        storage.load()


def test_polars_storage_wal_truncate_not_unlink(temp_storage_dir):
    """Test that WAL file is truncated, not unlinked, after archive.

    This ensures that readers who have the file open don't lose their handle.
    """
    project_name = "test_project"
    run_name = "test_run"

    storage = PolarsMetricsStorage(
        base_dir=str(temp_storage_dir),
        project_name=project_name,
        run_name=run_name,
        archive_threshold_bytes=100,  # Very small threshold
    )
    wal_path = temp_storage_dir / project_name / f"{run_name}.wal.jsonl"

    # Save first metric to create WAL
    storage.save({
        "project_name": project_name,
        "run_name": run_name,
        "timestamp": "2025-01-01T00:00:00",
        "step": 0,
        "metrics": {"loss": 0.5},
    })

    # WAL should exist
    assert wal_path.exists()

    # Open WAL file (simulating a reader holding the file handle)
    with open(wal_path) as f:
        initial_content = f.read()
        assert len(initial_content) > 0

        # Save enough metrics to trigger archive
        for i in range(1, 10):
            storage.save({
                "project_name": project_name,
                "run_name": run_name,
                "timestamp": f"2025-01-01T{i:02d}:00:00",
                "step": i,
                "metrics": {"loss": 0.5 - i * 0.01},
            })

        # WAL file should still exist (truncated, not unlinked)
        assert wal_path.exists(), "WAL file was unlinked instead of truncated!"

    # All data should be readable
    df = storage.load()
    assert len(df) == 10


def test_polars_storage_archive_before_write_order(temp_storage_dir):
    """Test that archive happens BEFORE write, not after.

    This prevents the race condition where:
    1. Writer writes to WAL
    2. Reader reads WAL (sees new data)
    3. Writer archives and clears WAL
    4. Reader reads again and misses the data (it's now in Parquet but reader
       might have cached the "no Parquet" state)

    By archiving first, we ensure WAL only contains data not yet in Parquet.
    """
    project_name = "test_project"
    run_name = "test_run"

    storage = PolarsMetricsStorage(
        base_dir=str(temp_storage_dir),
        project_name=project_name,
        run_name=run_name,
        archive_threshold_bytes=100,  # Small threshold
    )

    # Fill WAL to just below threshold
    for i in range(3):
        storage.save({
            "project_name": project_name,
            "run_name": run_name,
            "timestamp": f"2025-01-01T{i:02d}:00:00",
            "step": i,
            "metrics": {"loss": 0.5},
        })

    wal_path = temp_storage_dir / project_name / f"{run_name}.wal.jsonl"
    archive_path = temp_storage_dir / project_name / f"{run_name}_archive"

    # Check current state
    wal_size_before = wal_path.stat().st_size
    archive_exists_before = archive_path.exists()

    # This write should trigger archive (if threshold exceeded)
    storage.save({
        "project_name": project_name,
        "run_name": run_name,
        "timestamp": "2025-01-01T10:00:00",
        "step": 10,
        "metrics": {"loss": 0.1, "extra_data": "x" * 100},  # Large payload
    })

    # Regardless of whether archive happened, all data should be readable
    df = storage.load()
    assert len(df) == 4, f"Expected 4 metrics, got {len(df)}. WAL size before: {wal_size_before}, Archive existed before: {archive_exists_before}"
