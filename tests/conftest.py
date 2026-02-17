"""
Pytest configuration and shared fixtures.
"""

import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from aspara.catalog.project_catalog import ProjectInfo
from aspara.catalog.run_catalog import RunInfo
from aspara.dashboard.main import app
from aspara.models import MetricRecord


@pytest.fixture(autouse=True)
def clean_env_for_tests(monkeypatch):
    """Clean environment variables for test isolation.

    Ensures tests don't accidentally write to user's real data directory
    by clearing ASPARA_DATA_DIR and XDG_DATA_HOME environment variables.

    This fixture is applied automatically to all tests (autouse=True).
    """
    monkeypatch.delenv("ASPARA_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_temp_logs_dir():
    """Create a temporary directory for test logs."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_projects():
    """Mock project data."""
    return [
        ProjectInfo(
            name="test_project",
            run_count=3,
            last_update=datetime(2024, 1, 15, 10, 30, 0),
        ),
        ProjectInfo(
            name="empty_project",
            run_count=0,
            last_update=datetime(2024, 1, 10, 9, 0, 0),
        ),
    ]


@pytest.fixture
def mock_runs():
    """Mock run data.

    NOTE: This fixture is no longer used directly - the real MetricsReader
    reads data from actual JSONL files. These values are kept for reference
    but the actual param_count will be calculated by MetricsReader.
    """
    return {
        "test_project": [
            RunInfo(
                name="run_1",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                last_update=datetime(2024, 1, 15, 10, 30, 0),
                param_count=3,
                is_corrupted=False,
                error_message=None,
            ),
            RunInfo(
                name="run_2",
                start_time=datetime(2024, 1, 15, 9, 0, 0),
                last_update=datetime(2024, 1, 15, 9, 45, 0),
                param_count=3,
                is_corrupted=False,
                error_message=None,
            ),
            RunInfo(
                name="run_3",
                start_time=datetime(2024, 1, 14, 14, 0, 0),
                last_update=datetime(2024, 1, 14, 14, 20, 0),
                param_count=4,
                is_corrupted=False,
                error_message=None,
            ),
        ],
        "empty_project": [],
    }


@pytest.fixture
def mock_metrics():
    """Mock metrics data."""
    return {
        ("test_project", "run_1"): [
            MetricRecord(
                timestamp=datetime(2024, 1, 15, 10, 5, 0),
                step=0,
                metrics={"loss": 0.95, "accuracy": 0.12},
            ),
            MetricRecord(
                timestamp=datetime(2024, 1, 15, 10, 10, 0),
                step=1,
                metrics={"loss": 0.75, "accuracy": 0.45},
            ),
            MetricRecord(
                timestamp=datetime(2024, 1, 15, 10, 20, 0),
                step=2,
                metrics={"loss": 0.45, "accuracy": 0.78},
            ),
        ],
        ("test_project", "run_2"): [
            MetricRecord(
                timestamp=datetime(2024, 1, 15, 9, 15, 0),
                step=0,
                metrics={"loss": 0.85, "accuracy": 0.22},
            ),
            MetricRecord(
                timestamp=datetime(2024, 1, 15, 9, 30, 0),
                step=1,
                metrics={"loss": 0.65, "accuracy": 0.55},
            ),
        ],
        ("test_project", "run_3"): [
            MetricRecord(
                timestamp=datetime(2024, 1, 14, 14, 10, 0),
                step=0,
                metrics={"loss": 0.92, "accuracy": 0.15},
            ),
        ],
    }


@pytest.fixture
def setup_test_data(mock_projects, mock_runs, mock_metrics, mock_temp_logs_dir):
    """Fixture with test data written to actual JSONL files.

    NOTE: This fixture creates real JSONL files and patches the Catalog
    instances in router. This provides better test coverage.
    """
    from aspara.catalog import ProjectCatalog, RunCatalog

    mock_logs_dir = mock_temp_logs_dir

    # Create actual directory structure for projects and runs with real data
    for project_name, runs in mock_runs.items():
        project_dir = mock_logs_dir / project_name
        project_dir.mkdir(exist_ok=True)

        for run in runs:
            run_file = project_dir / f"{run.name}.jsonl"
            meta_file = project_dir / f"{run.name}.meta.json"

            # Write actual JSONL data for this run (metrics only)
            metrics_entries = mock_metrics.get((project_name, run.name), [])

            # Define params for each run (stored in metadata file)
            params_by_run = {
                "run_1": {"learning_rate": 0.01, "batch_size": 32, "epochs": 10},
                "run_2": {"learning_rate": 0.001, "batch_size": 64, "epochs": 5},
                "run_3": {"learning_rate": 0.005, "batch_size": 16, "epochs": 20, "optimizer": "sgd"},
            }
            params = params_by_run.get(run.name, {})

            # Write metrics to JSONL file
            with run_file.open("w") as f:
                for entry in metrics_entries:
                    # Convert MetricRecord to JSON (metrics only)
                    entry_dict = {
                        "timestamp": int(entry.timestamp.timestamp() * 1000),
                        "step": entry.step,
                        "metrics": entry.metrics,
                    }
                    # Write JSONL line
                    f.write(json.dumps(entry_dict) + "\n")

            # Write metadata to .meta.json file
            metadata = {
                "run_id": f"{run.name}_id",
                "tags": [],
                "notes": "",
                "params": params,
                "config": {},
                "artifacts": [],
                "summary": {},
                "is_finished": False,
                "exit_code": None,
                "start_time": run.start_time.isoformat() if run.start_time else None,
                "finish_time": None,
            }
            with meta_file.open("w") as f:
                json.dump(metadata, f, indent=2)

    # Create empty project directory
    empty_project_dir = mock_logs_dir / "empty_project"
    empty_project_dir.mkdir(exist_ok=True)

    # Create real Catalog instances
    project_catalog = ProjectCatalog(str(mock_logs_dir))
    run_catalog = RunCatalog(str(mock_logs_dir))

    # Configure the data directory using the new dependencies module
    from aspara.dashboard.dependencies import configure_data_dir

    configure_data_dir(str(mock_logs_dir))

    try:
        yield (project_catalog, run_catalog)
    finally:
        # Reset to default configuration after test
        configure_data_dir(None)


@pytest.fixture
def setup_test_data_with_corrupted(mock_temp_logs_dir):
    """Fixture with corrupted run data (empty JSONL files).

    NOTE: This fixture creates real empty JSONL files to simulate corruption
    and patches the Catalog instances in router.
    """
    from aspara.catalog import ProjectCatalog, RunCatalog

    mock_logs_dir = mock_temp_logs_dir

    # Create corrupted project with empty file
    project_dir = mock_logs_dir / "corrupted_project"
    project_dir.mkdir(exist_ok=True)

    # Create empty file to simulate corruption
    run_file = project_dir / "corrupted_run_empty.jsonl"
    run_file.touch()  # Empty file = corrupted

    # Create real Catalog instances
    project_catalog = ProjectCatalog(str(mock_logs_dir))
    run_catalog = RunCatalog(str(mock_logs_dir))

    # Configure the data directory using the new dependencies module
    from aspara.dashboard.dependencies import configure_data_dir

    configure_data_dir(str(mock_logs_dir))

    try:
        yield (project_catalog, run_catalog)
    finally:
        # Reset to default configuration after test
        configure_data_dir(None)
