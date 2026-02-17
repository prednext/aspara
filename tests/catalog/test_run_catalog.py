"""
Tests for RunCatalog
"""

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aspara.catalog import RunCatalog
from aspara.catalog.run_catalog import ProjectNotFoundError
from aspara.catalog.watcher import DataDirWatcher


@pytest.fixture
def temp_catalog_dir(tmp_path):
    """Fixture to provide a temporary directory"""
    return tmp_path


@pytest.fixture(autouse=True)
def reset_watcher():
    """Reset DataDirWatcher singleton between tests."""
    DataDirWatcher.reset_instance()
    yield
    DataDirWatcher.reset_instance()


def test_run_catalog_list(temp_catalog_dir):
    """Test that RunCatalog's list method works correctly"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create test directories and files
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()
    (project_dir / "run1.jsonl").write_text('{"metrics": {}}')
    (project_dir / "run2.jsonl").write_text('{"metrics": {}}')
    (project_dir / "not_a_run.txt").write_text("This is not a run file")

    # Get run list
    runs = catalog.get_runs("test_project")

    # Verify results
    assert len(runs) == 2
    run_names = [r.name for r in runs]
    assert "run1" in run_names
    assert "run2" in run_names
    assert "not_a_run.txt" not in run_names


def test_run_catalog_list_nonexistent_project(temp_catalog_dir):
    """Test that calling list on a non-existent project raises an exception"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Verify that an exception is raised for non-existent project
    with pytest.raises(ProjectNotFoundError):
        catalog.get_runs("non_existent_project")


@pytest.mark.asyncio
async def test_subscribe_single_run(temp_catalog_dir):
    """Test that subscribe() method can monitor a single run file"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create project directory and run file
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()
    run_file = project_dir / "test_run.jsonl"

    # Write initial data
    initial_data = {
        "type": "metrics",
        "timestamp": "2024-01-01T00:00:00Z",
        "run": "test_run",
        "project": "test_project",
        "step": 0,
        "metrics": {"loss": 0.5},
    }
    run_file.write_text(json.dumps(initial_data) + "\n")

    # Use epoch as since to get all data
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Start subscribe()
    watch_task = asyncio.create_task(collect_metrics_with_timeout(catalog.subscribe({"test_project": ["test_run"]}, since), timeout=2.0))

    # Wait a bit for file to be monitored
    await asyncio.sleep(0.5)

    # Add new metrics
    new_data = {
        "type": "metrics",
        "timestamp": "2024-01-01T00:00:01Z",
        "run": "test_run",
        "project": "test_project",
        "step": 1,
        "metrics": {"loss": 0.4},
    }
    with open(run_file, "a") as f:
        f.write(json.dumps(new_data) + "\n")

    # Collect metrics
    metrics = await watch_task

    # Verify that both existing and newly added metrics are detected
    assert len(metrics) >= 2
    assert any(m.step == 0 and m.metrics.get("loss") == 0.5 for m in metrics)
    assert any(m.step == 1 and m.metrics.get("loss") == 0.4 for m in metrics)


@pytest.mark.asyncio
async def test_subscribe_multiple_runs(temp_catalog_dir):
    """Test that subscribe() method can monitor multiple run files simultaneously"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create project directory and multiple run files
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()

    run_files = []
    for i in range(3):
        run_file = project_dir / f"run_{i}.jsonl"
        initial_data = {
            "type": "metrics",
            "timestamp": "2024-01-01T00:00:00Z",
            "run": f"run_{i}",
            "project": "test_project",
            "step": 0,
            "metrics": {"value": i},
        }
        run_file.write_text(json.dumps(initial_data) + "\n")
        run_files.append(run_file)

    # Use epoch as since to get all data
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Start subscribe()
    run_names = [f"run_{i}" for i in range(3)]
    watch_task = asyncio.create_task(collect_metrics_with_timeout(catalog.subscribe({"test_project": run_names}, since), timeout=2.0))

    # Wait a bit for file to be monitored
    await asyncio.sleep(0.5)

    # Add new metrics to each file
    for i, run_file in enumerate(run_files):
        new_data = {
            "type": "metrics",
            "timestamp": "2024-01-01T00:00:01Z",
            "run": f"run_{i}",
            "project": "test_project",
            "step": 1,
            "metrics": {"value": i * 10},
        }
        with open(run_file, "a") as f:
            f.write(json.dumps(new_data) + "\n")
        await asyncio.sleep(0.1)  # Small delay for file change detection

    # Collect metrics
    metrics = await watch_task

    # Verify that metrics are detected from all runs (both existing and new)
    assert len(metrics) >= 6  # 3 existing + 3 new
    run_names_detected = {m.run for m in metrics if m.step == 1}
    assert len(run_names_detected) == 3
    assert all(f"run_{i}" in run_names_detected for i in range(3))


@pytest.mark.asyncio
async def test_subscribe_nonexistent_file(temp_catalog_dir):
    """Test that subscribe() on a non-existent file returns nothing"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create project directory (but don't create run file)
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()

    # Use epoch as since
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Start subscribe() with timeout
    metrics = await collect_metrics_with_timeout(catalog.subscribe({"test_project": ["nonexistent_run"]}, since), timeout=0.5)

    # Verify that nothing is returned
    assert len(metrics) == 0


@pytest.mark.asyncio
async def test_subscribe_empty_list(temp_catalog_dir):
    """Test that subscribe() with an empty list returns nothing"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create project directory
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()

    # Use epoch as since
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Start subscribe() with empty list
    metrics = await collect_metrics_with_timeout(catalog.subscribe({"test_project": []}, since), timeout=0.5)

    # Verify that nothing is returned
    assert len(metrics) == 0


async def collect_metrics_with_timeout(async_gen, timeout=1.0):
    """Collect metrics from AsyncGenerator (with timeout)"""
    metrics = []

    async def _collect():
        async for metric in async_gen:
            metrics.append(metric)

    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(_collect(), timeout=timeout)
    return metrics


@pytest.mark.asyncio
async def test_subscribe_both_wal_and_jsonl_files(temp_catalog_dir):
    """Test that both WAL and JSONL files can be monitored when both exist"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create project directory
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()

    # Create both WAL and JSONL files
    wal_file = project_dir / "test_run.wal.jsonl"
    jsonl_file = project_dir / "test_run.jsonl"

    # Write initial data
    initial_wal_data = {
        "type": "metrics",
        "timestamp": "2024-01-01T00:00:00Z",
        "run": "test_run",
        "project": "test_project",
        "step": 0,
        "metrics": {"loss": 0.5},
    }
    initial_jsonl_data = {
        "type": "metrics",
        "timestamp": "2024-01-01T00:00:00Z",
        "run": "test_run",
        "project": "test_project",
        "step": 0,
        "metrics": {"accuracy": 0.8},
    }
    wal_file.write_text(json.dumps(initial_wal_data) + "\n")
    jsonl_file.write_text(json.dumps(initial_jsonl_data) + "\n")

    # Use epoch as since to get all data
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Start subscribe()
    watch_task = asyncio.create_task(collect_metrics_with_timeout(catalog.subscribe({"test_project": ["test_run"]}, since), timeout=3.0))

    # Wait a bit for file to be monitored
    await asyncio.sleep(0.5)

    # Add new metrics to WAL file
    new_wal_data = {
        "type": "metrics",
        "timestamp": "2024-01-01T00:00:01Z",
        "run": "test_run",
        "project": "test_project",
        "step": 1,
        "metrics": {"loss": 0.4},
    }
    with open(wal_file, "a") as f:
        f.write(json.dumps(new_wal_data) + "\n")

    await asyncio.sleep(0.5)

    # Add new metrics to JSONL file
    new_jsonl_data = {
        "type": "metrics",
        "timestamp": "2024-01-01T00:00:02Z",
        "run": "test_run",
        "project": "test_project",
        "step": 2,
        "metrics": {"accuracy": 0.85},
    }
    with open(jsonl_file, "a") as f:
        f.write(json.dumps(new_jsonl_data) + "\n")

    # Collect metrics
    metrics = await watch_task

    # Verify that metrics were received from both files (initial + new)
    assert len(metrics) >= 4  # 2 initial + 2 new
    steps = [m.step for m in metrics]
    assert 1 in steps  # From WAL file
    assert 2 in steps  # From JSONL file


@pytest.mark.asyncio
async def test_subscribe_with_since_filter(temp_catalog_dir):
    """Test that subscribe() filters records by since timestamp"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create project directory and run file
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()
    run_file = project_dir / "test_run.jsonl"

    # Write data with different timestamps
    old_data = {
        "type": "metrics",
        "timestamp": "2024-01-01T00:00:00Z",
        "run": "test_run",
        "project": "test_project",
        "step": 0,
        "metrics": {"loss": 0.5},
    }
    new_data = {
        "type": "metrics",
        "timestamp": "2024-01-02T00:00:00Z",
        "run": "test_run",
        "project": "test_project",
        "step": 1,
        "metrics": {"loss": 0.4},
    }
    run_file.write_text(json.dumps(old_data) + "\n" + json.dumps(new_data) + "\n")

    # Use since = 2024-01-01T12:00:00Z to filter out old data
    since = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Start subscribe()
    metrics = await collect_metrics_with_timeout(catalog.subscribe({"test_project": ["test_run"]}, since), timeout=0.5)

    # Verify that only new data is returned
    assert len(metrics) == 1
    assert metrics[0].step == 1
    assert metrics[0].metrics.get("loss") == 0.4


@pytest.mark.asyncio
async def test_subscribe_multiple_with_since_filter(temp_catalog_dir):
    """Test that subscribe() filters records by since timestamp"""

    catalog = RunCatalog(str(temp_catalog_dir))

    # Create project directory and run files
    project_dir = temp_catalog_dir / "test_project"
    project_dir.mkdir()

    # Create two run files with data from different times
    for run_name in ["run_1", "run_2"]:
        run_file = project_dir / f"{run_name}.jsonl"
        old_data = {
            "type": "metrics",
            "timestamp": "2024-01-01T00:00:00Z",
            "run": run_name,
            "project": "test_project",
            "step": 0,
            "metrics": {"value": 0},
        }
        new_data = {
            "type": "metrics",
            "timestamp": "2024-01-02T00:00:00Z",
            "run": run_name,
            "project": "test_project",
            "step": 1,
            "metrics": {"value": 1},
        }
        run_file.write_text(json.dumps(old_data) + "\n" + json.dumps(new_data) + "\n")

    # Use since = 2024-01-01T12:00:00Z to filter out old data
    since = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Start subscribe()
    metrics = await collect_metrics_with_timeout(catalog.subscribe({"test_project": ["run_1", "run_2"]}, since), timeout=0.5)

    # Verify that only new data is returned from both runs
    assert len(metrics) == 2
    assert all(m.step == 1 for m in metrics)
    run_names = {m.run for m in metrics}
    assert run_names == {"run_1", "run_2"}


class TestParseFilePath:
    """Tests for _parse_file_path() helper method."""

    def test_parse_jsonl_file(self, tmp_path):
        """Test parsing .jsonl file path."""
        catalog = RunCatalog(tmp_path)
        path = tmp_path / "project_a" / "run1.jsonl"
        result = catalog._parse_file_path(path)
        assert result == ("project_a", "run1", "metrics")

    def test_parse_wal_file(self, tmp_path):
        """Test parsing .wal.jsonl file path."""
        catalog = RunCatalog(tmp_path)
        path = tmp_path / "project_a" / "run1.wal.jsonl"
        result = catalog._parse_file_path(path)
        assert result == ("project_a", "run1", "wal")

    def test_parse_meta_file(self, tmp_path):
        """Test parsing .meta.json file path."""
        catalog = RunCatalog(tmp_path)
        path = tmp_path / "project_a" / "run1.meta.json"
        result = catalog._parse_file_path(path)
        assert result == ("project_a", "run1", "meta")

    def test_path_outside_data_dir(self, tmp_path):
        """Test path outside data_dir returns None."""
        catalog = RunCatalog(tmp_path)
        path = Path("/other/path/file.jsonl")
        assert catalog._parse_file_path(path) is None

    def test_nested_path_too_deep(self, tmp_path):
        """Test deeply nested path returns None."""
        catalog = RunCatalog(tmp_path)
        path = tmp_path / "project" / "subdir" / "run.jsonl"
        assert catalog._parse_file_path(path) is None

    def test_unknown_extension(self, tmp_path):
        """Test unknown file extension returns None."""
        catalog = RunCatalog(tmp_path)
        path = tmp_path / "project" / "file.txt"
        assert catalog._parse_file_path(path) is None

    def test_path_at_root_level(self, tmp_path):
        """Test file directly in data_dir returns None (needs project/run structure)."""
        catalog = RunCatalog(tmp_path)
        path = tmp_path / "run.jsonl"
        assert catalog._parse_file_path(path) is None


class TestSubscribe:
    """Tests for subscribe() method."""

    @pytest.mark.asyncio
    async def test_subscribe_multiple_projects(self, tmp_path):
        """Test subscribing to multiple projects simultaneously."""
        catalog = RunCatalog(tmp_path)

        # Create project directories and run files
        for project in ["project_a", "project_b"]:
            project_dir = tmp_path / project
            project_dir.mkdir()
            run_file = project_dir / "run1.jsonl"
            data = {
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "run": "run1",
                "project": project,
                "step": 0,
                "metrics": {"value": 1},
            }
            run_file.write_text(json.dumps(data) + "\n")

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"project_a": ["run1"], "project_b": ["run1"]}

        metrics = await collect_metrics_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        # Verify records from both projects
        assert len(metrics) == 2
        projects = {m.project for m in metrics}
        assert projects == {"project_a", "project_b"}

    @pytest.mark.asyncio
    async def test_file_change_detection(self, tmp_path):
        """Test that file changes are detected and yielded."""
        catalog = RunCatalog(tmp_path)

        # Create project directory and run file
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        initial_data = {
            "type": "metrics",
            "timestamp": "2024-01-01T00:00:00Z",
            "run": "run1",
            "project": "test_project",
            "step": 0,
            "metrics": {"value": 1},
        }
        run_file.write_text(json.dumps(initial_data) + "\n")

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        watch_task = asyncio.create_task(collect_metrics_with_timeout(catalog.subscribe(targets, since), timeout=2.0))

        await asyncio.sleep(0.5)

        # Append new data
        new_data = {
            "type": "metrics",
            "timestamp": "2024-01-01T00:00:01Z",
            "run": "run1",
            "project": "test_project",
            "step": 1,
            "metrics": {"value": 2},
        }
        with open(run_file, "a") as f:
            f.write(json.dumps(new_data) + "\n")

        metrics = await watch_task

        # Verify both initial and new records
        assert len(metrics) >= 2
        steps = [m.step for m in metrics]
        assert 0 in steps
        assert 1 in steps

    @pytest.mark.asyncio
    async def test_ignores_unwatched_projects(self, tmp_path):
        """Test that changes to non-target projects are ignored."""
        catalog = RunCatalog(tmp_path)

        # Create two projects
        for project in ["watched", "ignored"]:
            project_dir = tmp_path / project
            project_dir.mkdir()
            run_file = project_dir / "run1.jsonl"
            data = {
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "run": "run1",
                "project": project,
                "step": 0,
                "metrics": {"value": 1},
            }
            run_file.write_text(json.dumps(data) + "\n")

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        # Only watch "watched" project
        targets = {"watched": ["run1"]}

        metrics = await collect_metrics_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        # Verify only watched project is returned
        assert len(metrics) == 1
        assert metrics[0].project == "watched"

    @pytest.mark.asyncio
    async def test_ignores_unwatched_runs(self, tmp_path):
        """Test that changes to non-target runs are ignored."""
        catalog = RunCatalog(tmp_path)

        # Create project with two runs
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        for run_name in ["watched_run", "ignored_run"]:
            run_file = project_dir / f"{run_name}.jsonl"
            data = {
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "run": run_name,
                "project": "test_project",
                "step": 0,
                "metrics": {"value": 1},
            }
            run_file.write_text(json.dumps(data) + "\n")

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        # Only watch "watched_run"
        targets = {"test_project": ["watched_run"]}

        metrics = await collect_metrics_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        # Verify only watched run is returned
        assert len(metrics) == 1
        assert metrics[0].run == "watched_run"

    @pytest.mark.asyncio
    async def test_status_record_on_meta_change(self, tmp_path):
        """Test StatusRecord is yielded when meta file changes."""
        catalog = RunCatalog(tmp_path)

        # Create project directory with run and meta files
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        run_file = project_dir / "run1.jsonl"
        run_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"value": 1},
            })
            + "\n"
        )

        meta_file = project_dir / "run1.meta.json"
        meta_file.write_text(json.dumps({"status": "wip", "is_finished": False}))

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        watch_task = asyncio.create_task(collect_metrics_with_timeout(catalog.subscribe(targets, since), timeout=2.0))

        await asyncio.sleep(0.5)

        # Update status in meta file
        meta_file.write_text(json.dumps({"status": "completed", "is_finished": True}))

        records = await watch_task

        # Verify StatusRecord was yielded
        from aspara.models import StatusRecord

        status_records = [r for r in records if isinstance(r, StatusRecord)]
        assert len(status_records) >= 1
        assert any(r.status == "completed" for r in status_records)

    @pytest.mark.asyncio
    async def test_subscribe_all_runs_with_none(self, tmp_path):
        """Test subscribing to all runs when run list is None."""
        catalog = RunCatalog(tmp_path)

        # Create project with multiple runs
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        for run_name in ["run1", "run2", "run3"]:
            run_file = project_dir / f"{run_name}.jsonl"
            data = {
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "run": run_name,
                "project": "test_project",
                "step": 0,
                "metrics": {"value": 1},
            }
            run_file.write_text(json.dumps(data) + "\n")

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        # Subscribe to all runs with None
        targets = {"test_project": None}

        metrics = await collect_metrics_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        # Verify all runs are returned
        assert len(metrics) == 3
        run_names = {m.run for m in metrics}
        assert run_names == {"run1", "run2", "run3"}

    @pytest.mark.asyncio
    async def test_empty_targets(self, tmp_path):
        """Test that empty targets returns nothing."""
        catalog = RunCatalog(tmp_path)

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets: dict[str, list[str] | None] = {}

        metrics = await collect_metrics_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        assert len(metrics) == 0


class TestRunCatalogMetadata:
    """Tests for RunCatalog metadata methods.

    These tests verify that RunCatalog uses RunMetadataStorage (not ProjectMetadataStorage)
    for metadata operations. The correct behavior is:
    - Reads/writes {data_dir}/{project}/{run}.meta.json (run format)
    - NOT {data_dir}/{project}/{run}/metadata.json (project format)
    """

    def test_get_metadata_reads_meta_json(self, tmp_path):
        """Verify get_metadata reads from {run}.meta.json, not {run}/metadata.json."""
        catalog = RunCatalog(tmp_path)

        # Create project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Create correct .meta.json file
        correct_meta = project_dir / "test_run.meta.json"
        correct_meta.write_text(
            json.dumps({
                "run_id": "correct-id",
                "tags": ["correct"],
                "notes": "Correct notes from .meta.json",
                "params": {},
                "config": {},
                "artifacts": [],
                "summary": {},
                "is_finished": False,
                "exit_code": None,
                "status": "wip",
                "start_time": None,
                "finish_time": None,
            })
        )

        # Create wrong metadata.json file (project format)
        wrong_dir = project_dir / "test_run"
        wrong_dir.mkdir()
        wrong_meta = wrong_dir / "metadata.json"
        wrong_meta.write_text(
            json.dumps({
                "tags": ["wrong"],
                "notes": "Wrong notes from metadata.json",
            })
        )

        # get_metadata should read from .meta.json, not metadata.json
        metadata = catalog.get_metadata("test_project", "test_run")

        assert metadata["notes"] == "Correct notes from .meta.json"
        assert metadata["tags"] == ["correct"]
        assert metadata["run_id"] == "correct-id"

    def test_update_metadata_writes_meta_json(self, tmp_path):
        """Verify update_metadata writes to {run}.meta.json."""
        catalog = RunCatalog(tmp_path)

        # Create project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Update metadata
        result = catalog.update_metadata(
            "test_project",
            "test_run",
            {
                "notes": "Updated notes",
                "tags": ["tag1", "tag2"],
            },
        )

        # Verify .meta.json was created
        correct_meta = project_dir / "test_run.meta.json"
        assert correct_meta.exists()

        # Verify wrong location was NOT created
        wrong_meta = project_dir / "test_run" / "metadata.json"
        assert not wrong_meta.exists()

        # Verify content
        with open(correct_meta) as f:
            saved = json.load(f)
        assert saved["notes"] == "Updated notes"
        assert saved["tags"] == ["tag1", "tag2"]

        # Verify return value
        assert result["notes"] == "Updated notes"
        assert result["tags"] == ["tag1", "tag2"]

    def test_delete_metadata_deletes_meta_json(self, tmp_path):
        """Verify delete_metadata deletes {run}.meta.json."""
        catalog = RunCatalog(tmp_path)

        # Create project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Create .meta.json file
        meta_file = project_dir / "test_run.meta.json"
        meta_file.write_text(
            json.dumps({
                "run_id": "test-id",
                "tags": [],
                "notes": "",
                "params": {},
                "config": {},
                "artifacts": [],
                "summary": {},
                "is_finished": False,
                "exit_code": None,
                "status": "wip",
                "start_time": None,
                "finish_time": None,
            })
        )

        # Delete metadata
        result = catalog.delete_metadata("test_project", "test_run")

        assert result is True
        assert not meta_file.exists()

    def test_delete_metadata_returns_false_if_not_exists(self, tmp_path):
        """Verify delete_metadata returns False if file doesn't exist."""
        catalog = RunCatalog(tmp_path)

        # Create project directory (but no meta file)
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        result = catalog.delete_metadata("test_project", "test_run")

        assert result is False

    def test_metadata_roundtrip(self, tmp_path):
        """Test full update/get roundtrip with run-specific fields."""
        catalog = RunCatalog(tmp_path)

        # Create project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Update metadata
        catalog.update_metadata(
            "test_project",
            "test_run",
            {
                "notes": "Test notes",
                "tags": ["ml", "experiment"],
            },
        )

        # Get metadata back
        metadata = catalog.get_metadata("test_project", "test_run")

        assert metadata["notes"] == "Test notes"
        assert metadata["tags"] == ["ml", "experiment"]

        # Update again
        catalog.update_metadata(
            "test_project",
            "test_run",
            {
                "notes": "Updated notes",
            },
        )

        # Get again - tags should be preserved
        metadata = catalog.get_metadata("test_project", "test_run")

        assert metadata["notes"] == "Updated notes"
        assert metadata["tags"] == ["ml", "experiment"]
