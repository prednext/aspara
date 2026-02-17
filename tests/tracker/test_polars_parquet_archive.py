"""
Tests for Polars Parquet archive functionality with date partitioning
"""

import shutil
from datetime import datetime, timedelta

import pytest

from aspara.storage import PolarsMetricsStorage


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Fixture providing temporary directory for tests"""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir()
    yield storage_dir
    # Cleanup after test
    if storage_dir.exists():
        shutil.rmtree(storage_dir)


def test_parquet_archive_with_partition_by(temp_storage_dir):
    """Test that old data is archived to Parquet with date partitioning"""
    # Use 1 byte threshold - force WAL archive immediately
    storage = PolarsMetricsStorage(
        base_dir=str(temp_storage_dir),
        project_name="test_project",
        run_name="test_run",
        archive_threshold_bytes=1,  # Force WAL archive immediately
    )

    # Save old metrics (will be archived)
    old_timestamp = int((datetime.now() - timedelta(days=3)).timestamp() * 1000)
    old_data = {
        "timestamp": old_timestamp,
        "step": 1,
        "metrics": {"loss": 0.5, "accuracy": 0.8},
    }
    storage.save(old_data)

    # Save intermediate metrics
    intermediate_timestamp = int((datetime.now() - timedelta(days=2)).timestamp() * 1000)
    intermediate_data = {
        "timestamp": intermediate_timestamp,
        "step": 2,
        "metrics": {"loss": 0.4, "accuracy": 0.85},
    }
    storage.save(intermediate_data)

    # Save recent metrics (this will trigger archiving)
    recent_timestamp = int(datetime.now().timestamp() * 1000)
    recent_data = {
        "timestamp": recent_timestamp,
        "step": 3,
        "metrics": {"loss": 0.3, "accuracy": 0.9},
    }
    storage.save(recent_data)

    # Check that archive directory exists
    archive_path = storage._get_archive_path()
    assert archive_path.exists(), "Archive directory should exist"

    # Check that Parquet files are created with date partitioning
    parquet_files = list(archive_path.rglob("*.parquet"))
    assert len(parquet_files) > 0, "Parquet files should be created"

    # Verify date-based directory structure exists (partition_by creates date=YYYY-MM-DD folders)
    date_dirs = [d for d in archive_path.iterdir() if d.is_dir() and d.name.startswith("date=")]
    assert len(date_dirs) > 0, "Date partition directories should exist"

    # Load all metrics and verify all data (archived + recent) are accessible
    all_metrics = storage.load()
    import polars as pl

    assert isinstance(all_metrics, pl.DataFrame)
    assert len(all_metrics) == 3, "Should load all metrics (archived + recent)"

    # Verify metrics are sorted by timestamp
    timestamps = all_metrics.select("timestamp").to_series().to_list()
    assert timestamps[0] < timestamps[1] < timestamps[2], "Metrics should be sorted by timestamp"


def test_read_from_parquet_only(temp_storage_dir):
    """Test reading metrics when only Parquet archives exist (no WAL)"""
    storage = PolarsMetricsStorage(
        base_dir=str(temp_storage_dir),
        project_name="test_project",
        run_name="test_run",
        archive_threshold_bytes=1,
    )

    # Save old metrics that will be archived
    old_timestamp = int((datetime.now() - timedelta(days=3)).timestamp() * 1000)
    old_data = {
        "timestamp": old_timestamp,
        "step": 1,
        "metrics": {"loss": 0.5},
    }
    storage.save(old_data)

    # Trigger archiving by saving recent data
    recent_timestamp = int(datetime.now().timestamp() * 1000)
    recent_data = {
        "timestamp": recent_timestamp,
        "step": 2,
        "metrics": {"loss": 0.3},
    }
    storage.save(recent_data)

    # Should be able to read from Parquet archives
    metrics = storage.load()
    assert len(metrics) > 0, "Should be able to read from Parquet archives"


def test_no_archive_if_no_old_data(temp_storage_dir):
    """Test that archiving is skipped if WAL threshold is not reached"""
    storage = PolarsMetricsStorage(
        base_dir=str(temp_storage_dir),
        project_name="test_project",
        run_name="test_run",
        archive_threshold_bytes=1024 * 1024,  # 1MB threshold - won't be reached
    )

    # Save only a small amount of data (won't reach threshold)
    recent_timestamp = int(datetime.now().timestamp() * 1000)
    data = {
        "timestamp": recent_timestamp,
        "step": 1,
        "metrics": {"loss": 0.5},
    }
    storage.save(data)

    # Archive directory should not exist (WAL threshold not reached)
    archive_path = storage._get_archive_path()
    # Note: archive_path directory might exist but should have no parquet files
    if archive_path.exists():
        parquet_files = list(archive_path.rglob("*.parquet"))
        assert len(parquet_files) == 0, "No Parquet files should be created when WAL threshold not reached"
