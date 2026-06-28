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


class TestProcessMetricsChangeTruncation:
    """Tests for _process_metrics_change handling of file truncation.

    When a WAL file is truncated (e.g. by PolarsMetricsStorage._clear_wal after
    archiving), the watcher's tracked file size becomes larger than the actual
    file. Without recovery logic, f.seek(current_size) seeks past EOF and the
    new content appended after truncation is silently lost forever.
    """

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton instance before and after each test."""
        DataDirWatcher.reset_instance()
        yield
        DataDirWatcher.reset_instance()

    def _make_record_line(self, step: int, loss: float) -> str:
        return (
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": step,
                "metrics": {"loss": loss},
            })
            + "\n"
        )

    @pytest.mark.asyncio
    async def test_recovers_after_truncate(self, tmp_path):
        """After truncate+append, new content is read despite stale tracked size."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        # Grow the file well past the new single record size, as a real WAL does
        # before _clear_wal truncates it.
        initial_content = "".join(self._make_record_line(i, 0.5) for i in range(50))
        run_file.write_text(initial_content)

        watcher = DataDirWatcher(tmp_path)
        resolved = run_file.resolve()

        # Simulate initial read populating _file_sizes with the post-read size.
        content, end_pos = watcher._read_file_with_strategy(resolved)
        watcher._file_sizes[resolved] = end_pos
        stale_size = watcher._file_sizes[resolved]
        assert stale_size > 0

        # Truncate the file (as _clear_wal does) and append fresh content.
        run_file.write_text(self._make_record_line(10, 0.1))
        assert run_file.stat().st_size < stale_size

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        records = await watcher._process_metrics_change(resolved, "test_project", "run1", since)

        # The new record must be recovered, not silently dropped.
        assert len(records) == 1
        assert records[0].step == 10
        # And the tracked size must be reset to a sane value.
        assert watcher._file_sizes[resolved] == run_file.stat().st_size

    @pytest.mark.asyncio
    async def test_normal_append_still_works(self, tmp_path):
        """Normal append (no truncation) still reads only the new tail."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        run_file = project_dir / "run1.jsonl"
        run_file.write_text(self._make_record_line(0, 0.5))

        watcher = DataDirWatcher(tmp_path)
        resolved = run_file.resolve()
        content, end_pos = watcher._read_file_with_strategy(resolved)
        watcher._file_sizes[resolved] = end_pos

        # Append new content (file grows).
        with open(run_file, "a") as f:
            f.write(self._make_record_line(1, 0.4))

        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        records = await watcher._process_metrics_change(resolved, "test_project", "run1", since)

        # Only the newly appended record should be returned.
        assert len(records) == 1
        assert records[0].step == 1


class TestDispatchLoopSymlinkSkip:
    """Tests that the dispatch loop skips symlinks.

    The initial read in _read_initial_data already skips symlinks, but the
    dispatch loop must do the same so a symlink created after subscription
    cannot bypass the check and read files outside data_dir.
    """

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton instance before and after each test."""
        DataDirWatcher.reset_instance()
        yield
        DataDirWatcher.reset_instance()

    @pytest.mark.asyncio
    async def test_dispatch_skips_symlink(self, tmp_path):
        """A symlink inside data_dir must not yield records from its target."""
        import os

        if os.name == "nt":
            pytest.skip("Symlink behavior differs on Windows")

        # Create a target file outside data_dir with sensitive content.
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        target_file = outside_dir / "secret.jsonl"
        target_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"secret": 999},
            })
            + "\n"
        )

        # Create project dir inside data_dir with a legitimate run.
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        legit_file = project_dir / "legit.jsonl"
        legit_file.write_text(
            json.dumps({
                "type": "metrics",
                "timestamp": "2024-01-01T00:00:00Z",
                "step": 0,
                "metrics": {"loss": 0.5},
            })
            + "\n"
        )

        # Create a symlink inside data_dir pointing to the outside file.
        symlink_path = project_dir / "evil.jsonl"
        os.symlink(target_file, symlink_path)
        assert symlink_path.is_symlink()

        watcher = await DataDirWatcher.get_instance(tmp_path)
        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
        targets = {"test_project": None}  # Watch all runs

        records = await collect_records_with_timeout(watcher.subscribe(targets, since), timeout=1.0)

        # The legit run should produce a record, but the symlink must NOT.
        metric_records = [r for r in records if isinstance(r, MetricRecord)]
        run_names = {r.run for r in metric_records}
        assert "legit" in run_names
        assert "evil" not in run_names
        # The secret metric value must never appear.
        for r in metric_records:
            assert "secret" not in r.metrics


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
