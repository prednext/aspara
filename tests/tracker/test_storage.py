"""
Tests for Aspara tracker storage backend
"""

import json
import shutil

import pytest

from aspara.exceptions import RunNotFoundError
from aspara.storage.metrics import JsonlMetricsStorage


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Fixture to provide a temporary directory for testing"""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir()
    yield storage_dir
    # Remove directory after test
    if storage_dir.exists():
        shutil.rmtree(storage_dir)


def test_file_storage_backend_init(temp_storage_dir):
    """Test that JsonlMetricsStorage initialization works correctly"""

    # Initialize storage backend
    storage = JsonlMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run")

    # Verify that some value is returned
    assert storage

    # Verify that base directory is created
    assert temp_storage_dir.exists()
    assert temp_storage_dir.is_dir()


def test_file_storage_save(temp_storage_dir):
    """Test that JsonlMetricsStorage's save method works correctly"""

    # Initialize storage backend
    storage = JsonlMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run_1")

    # Test metrics data
    metrics_data = {
        "timestamp": "2024-01-15T10:05:00",
        "step": 0,
        "metrics": {"loss": 0.95, "accuracy": 0.12},
    }

    # Save metrics
    result = storage.save(metrics_data)

    # Verify that empty string is returned
    assert result == ""

    # Verify that project directory is created
    project_dir = temp_storage_dir / "test_project"
    assert project_dir.exists()
    assert project_dir.is_dir()

    # Verify that run file is created
    run_file = project_dir / "test_run_1.jsonl"
    assert run_file.exists()
    assert run_file.is_file()

    # Verify file contents
    with open(run_file) as f:
        line = f.readline().strip()
        saved_data = json.loads(line)
        assert saved_data["metrics"]["loss"] == 0.95


def test_file_storage_load(temp_storage_dir):
    """Test that JsonlMetricsStorage's load method works correctly"""

    # Initialize storage backend
    storage = JsonlMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="test_run_1")

    # Create test directories and files
    project_dir = temp_storage_dir / "test_project"
    project_dir.mkdir(parents=True)

    run_file = project_dir / "test_run_1.jsonl"

    # Write test data to file
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

    with open(run_file, "w") as f:
        for item in test_data:
            f.write(json.dumps(item) + "\n")

    # Get metrics
    result = storage.load()

    # Verify results - DataFrame is returned
    import polars as pl

    assert isinstance(result, pl.DataFrame)
    assert len(result) == 2
    assert "timestamp" in result.columns
    assert "step" in result.columns
    assert "_loss" in result.columns
    assert "_accuracy" in result.columns

    # Verify metric values
    assert result.filter(pl.col("step") == 1).select("_loss").item() == 0.5
    assert result.filter(pl.col("step") == 2).select("_accuracy").item() == 0.85

    # Get only specific metrics
    result = storage.load(metric_names=["loss"])

    # Verify that loss is included in both data entries
    assert len(result) == 2
    assert "_loss" in result.columns
    assert "_accuracy" not in result.columns

    # Verify that an exception is raised for non-existent run ID
    storage_non_existent = JsonlMetricsStorage(base_dir=str(temp_storage_dir), project_name="test_project", run_name="non_existent_run")
    with pytest.raises(RunNotFoundError):
        storage_non_existent.load()
