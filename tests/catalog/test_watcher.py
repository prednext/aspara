"""
Tests for DataDirWatcher and subscribe() method.
"""

import asyncio
import contextlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aspara.catalog import DataDirWatcher, RunCatalog
from aspara.models import MetricRecord, StatusRecord


async def collect_records_with_timeout(async_gen, timeout=1.0):
    """Collect records from AsyncGenerator (with timeout)."""
    records = []

    async def _collect():
        async for record in async_gen:
            records.append(record)

    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(_collect(), timeout=timeout)
    return records


class TestDataDirWatcher:
    """Tests for DataDirWatcher class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton instance before and after each test."""
        DataDirWatcher.reset_instance()
        yield
        DataDirWatcher.reset_instance()

    @pytest.mark.asyncio
    async def test_get_instance_creates_singleton(self, tmp_path):
        """Test that get_instance returns the same instance."""
        watcher1 = await DataDirWatcher.get_instance(tmp_path)
        watcher2 = await DataDirWatcher.get_instance(tmp_path)

        assert watcher1 is watcher2
        assert watcher1.data_dir == tmp_path

    @pytest.mark.asyncio
    async def test_subscribe_reads_initial_data(self, tmp_path):
        """Test that subscribe yields initial data from existing files."""
        # Create project and run file
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        run_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"loss": 0.5},
            })
            + "\n"
        )

        watcher = await DataDirWatcher.get_instance(tmp_path)
        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        records = await collect_records_with_timeout(watcher.subscribe(targets, since), timeout=0.5)

        assert len(records) >= 1
        assert any(isinstance(r, MetricRecord) and r.step == 0 for r in records)

    @pytest.mark.asyncio
    async def test_subscribe_detects_file_changes(self, tmp_path):
        """Test that subscribe yields new records when files change."""
        # Create project and run file
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        run_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"loss": 0.5},
            })
            + "\n"
        )

        watcher = await DataDirWatcher.get_instance(tmp_path)
        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        # Start subscription
        watch_task = asyncio.create_task(collect_records_with_timeout(watcher.subscribe(targets, since), timeout=2.0))

        # Wait for watcher to start
        await asyncio.sleep(0.5)

        # Add new data
        with open(run_file, "a") as f:
            f.write(
                json.dumps({
                    "type": "metrics",
                    "timestamp": "2024-01-01T00:00:01Z",
                    "step": 1,
                    "metrics": {"loss": 0.4},
                })
                + "\n"
            )

        records = await watch_task

        assert len(records) >= 2
        steps = [r.step for r in records if isinstance(r, MetricRecord)]
        assert 0 in steps
        assert 1 in steps

    @pytest.mark.asyncio
    async def test_subscribe_starts_dispatch_task(self, tmp_path):
        """Test that subscribing starts the dispatch task and shares the watcher."""
        # Create project with data
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        run_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"loss": 0.5},
            })
            + "\n"
        )

        watcher = await DataDirWatcher.get_instance(tmp_path)
        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        # Initially no dispatch task
        assert watcher._task is None

        # Start a subscription (will start dispatch task)
        records = await collect_records_with_timeout(watcher.subscribe(targets, since), timeout=0.5)

        # Should have received the initial record
        assert len(records) >= 1

        # After subscription ends, dispatch task should stop (no more subscribers)
        await asyncio.sleep(0.2)
        assert watcher.subscription_count == 0

    @pytest.mark.asyncio
    async def test_subscription_count_decreases_on_unsubscribe(self, tmp_path):
        """Test that subscription count decreases when subscribers leave."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        run_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"loss": 0.5},
            })
            + "\n"
        )

        watcher = await DataDirWatcher.get_instance(tmp_path)
        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        # Start subscription
        async def subscribe_briefly():
            async for _ in watcher.subscribe(targets, since):
                break  # Exit after first record

        await subscribe_briefly()
        await asyncio.sleep(0.1)

        # Subscription should be cleaned up
        assert watcher.subscription_count == 0

    @pytest.mark.asyncio
    async def test_data_dir_is_resolved_to_absolute_path(self, tmp_path):
        """Test that data_dir is resolved to absolute path.

        This test ensures that even when a relative path is passed to
        DataDirWatcher, it gets resolved to an absolute path. This is
        critical because awatch reports absolute paths, and comparison
        would fail if data_dir remains relative.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path.parent)
            relative_path = Path(tmp_path.name)  # Relative path like "pytest-123"

            watcher = await DataDirWatcher.get_instance(relative_path)

            assert watcher.data_dir.is_absolute()
            assert watcher.data_dir == tmp_path
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_subscribe_detects_changes_with_relative_path(self, tmp_path):
        """Test that file changes are detected when using relative path.

        This test verifies that the watcher correctly detects file changes
        even when initialized with a relative path. Without proper path
        resolution, awatch's absolute paths wouldn't match the relative
        data_dir, causing all events to be ignored.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path.parent)
            relative_path = Path(tmp_path.name)

            # Create project and initial file
            project_dir = relative_path / "test_project"
            project_dir.mkdir(parents=True)
            run_file = project_dir / "run1.jsonl"
            run_file.write_text(
                json.dumps({
                    "type": "metrics",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "step": 0,
                    "metrics": {"loss": 0.5},
                })
                + "\n"
            )

            watcher = await DataDirWatcher.get_instance(relative_path)
            since = datetime(1970, 1, 1, tzinfo=timezone.utc)
            targets = {"test_project": ["run1"]}

            # Start subscription
            watch_task = asyncio.create_task(collect_records_with_timeout(watcher.subscribe(targets, since), timeout=2.0))

            # Wait for watcher to start
            await asyncio.sleep(0.5)

            # Add new data
            with open(run_file, "a") as f:
                f.write(
                    json.dumps({
                        "type": "metrics",
                        "timestamp": "2024-01-01T00:00:01Z",
                        "step": 1,
                        "metrics": {"loss": 0.4},
                    })
                    + "\n"
                )

            records = await watch_task

            assert len(records) >= 2
            steps = [r.step for r in records if hasattr(r, "step")]
            assert 0 in steps
            assert 1 in steps
        finally:
            os.chdir(original_cwd)


class TestRunCatalogSubscribe:
    """Tests for RunCatalog.subscribe() method."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton instance before and after each test."""
        DataDirWatcher.reset_instance()
        yield
        DataDirWatcher.reset_instance()

    @pytest.mark.asyncio
    async def test_subscribe_single_run(self, tmp_path):
        """Test subscribe for a single run."""
        catalog = RunCatalog(tmp_path)

        # Create project and run file
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        run_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"loss": 0.5},
            })
            + "\n"
        )

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        records = await collect_records_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        assert len(records) >= 1
        assert records[0].project == "test_project"
        assert records[0].run == "run1"

    @pytest.mark.asyncio
    async def test_subscribe_multiple_runs(self, tmp_path):
        """Test subscribe for multiple runs."""
        catalog = RunCatalog(tmp_path)

        # Create project and multiple run files
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        for run_name in ["run1", "run2"]:
            run_file = project_dir / f"{run_name}.jsonl"
            run_file.write_text(
                json.dumps({
                    "type": "metrics",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "step": 0,
                    "metrics": {"loss": 0.5},
                })
                + "\n"
            )

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": ["run1", "run2"]}

        records = await collect_records_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        assert len(records) >= 2
        run_names = {r.run for r in records}
        assert run_names == {"run1", "run2"}

    @pytest.mark.asyncio
    async def test_subscribe_all_runs_with_none(self, tmp_path):
        """Test subscribe for all runs when run list is None."""
        catalog = RunCatalog(tmp_path)

        # Create project with multiple runs
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        for run_name in ["run1", "run2", "run3"]:
            run_file = project_dir / f"{run_name}.jsonl"
            run_file.write_text(
                json.dumps({
                    "type": "metrics",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "step": 0,
                    "metrics": {"value": 1},
                })
                + "\n"
            )

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": None}

        records = await collect_records_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        assert len(records) == 3
        run_names = {r.run for r in records}
        assert run_names == {"run1", "run2", "run3"}

    @pytest.mark.asyncio
    async def test_subscribe_multiple_projects(self, tmp_path):
        """Test subscribe for multiple projects."""
        catalog = RunCatalog(tmp_path)

        # Create multiple projects
        for project in ["project_a", "project_b"]:
            project_dir = tmp_path / project
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

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"project_a": ["run1"], "project_b": ["run1"]}

        records = await collect_records_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        assert len(records) == 2
        projects = {r.project for r in records}
        assert projects == {"project_a", "project_b"}

    @pytest.mark.asyncio
    async def test_subscribe_filters_by_since(self, tmp_path):
        """Test that subscribe filters records by since timestamp."""
        catalog = RunCatalog(tmp_path)

        # Create project and run file with old and new data
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        run_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"loss": 0.5},
            })
            + "\n"
            + json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-02T00:00:00Z",
                "step": 1,
                "metrics": {"loss": 0.4},
            })
            + "\n"
        )

        # Only get data from Jan 1 12:00 onwards
        since = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        targets = {"test_project": ["run1"]}

        records = await collect_records_with_timeout(catalog.subscribe(targets, since), timeout=0.5)

        assert len(records) == 1
        assert records[0].step == 1

    @pytest.mark.asyncio
    async def test_subscribe_status_change(self, tmp_path):
        """Test that subscribe yields StatusRecord on meta file change."""
        catalog = RunCatalog(tmp_path)

        # Create project with run and meta files
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

        watch_task = asyncio.create_task(collect_records_with_timeout(catalog.subscribe(targets, since), timeout=2.0))

        await asyncio.sleep(0.5)

        # Update status
        meta_file.write_text(json.dumps({"status": "completed", "is_finished": True}))

        records = await watch_task

        # Should have at least one StatusRecord
        status_records = [r for r in records if isinstance(r, StatusRecord)]
        assert len(status_records) >= 1
        assert any(r.status == "completed" for r in status_records)
