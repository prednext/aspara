"""
DataDirWatcher - Singleton watcher for data directory.

This module provides a centralized file watcher service that uses a single
inotify watcher for the entire data directory. Multiple SSE connections
subscribe to this service, reducing inotify file descriptor usage.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from watchfiles import awatch

from aspara.models import MetricRecord, RunStatus, StatusRecord
from aspara.utils.timestamp import parse_to_datetime
from aspara.utils.validators import validate_name

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    """Subscription to data directory changes."""

    id: str
    targets: Mapping[str, list[str] | None]  # project -> runs (None means all runs)
    since: datetime
    queue: asyncio.Queue[MetricRecord | StatusRecord | None] = field(default_factory=asyncio.Queue)


class DataDirWatcher:
    """Singleton watcher for data directory.

    This class provides a single inotify watcher for the entire data directory,
    allowing multiple SSE connections to subscribe without consuming additional
    file descriptors.
    """

    # Size thresholds for initial read strategy
    LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB
    TAIL_READ_SIZE = 64 * 1024  # Read last 64KB for large files

    _instance: DataDirWatcher | None = None
    _lock: asyncio.Lock | None = None

    def __init__(self, data_dir: Path) -> None:
        """Initialize the watcher.

        Note: Use get_instance() to get the singleton instance.

        Args:
            data_dir: Base directory for data storage
        """
        # Resolve to absolute path for consistent comparison with awatch paths
        self.data_dir = data_dir.resolve()
        self._subscriptions: dict[str, Subscription] = {}
        self._task: asyncio.Task[None] | None = None
        self._instance_lock = asyncio.Lock()
        # Track file sizes for incremental reading
        self._file_sizes: dict[Path, int] = {}
        # Track run statuses for change detection
        self._run_statuses: dict[tuple[str, str], str | None] = {}

    @classmethod
    async def get_instance(cls, data_dir: Path) -> DataDirWatcher:
        """Get or create singleton instance.

        Args:
            data_dir: Base directory for data storage

        Returns:
            DataDirWatcher singleton instance
        """
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(data_dir)
                logger.info(f"[Watcher] Created singleton DataDirWatcher for {data_dir}")
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Used for testing."""
        cls._instance = None
        cls._lock = None

    def _parse_file_path(self, file_path: Path) -> tuple[str, str, str] | None:
        """Parse file path to extract project, run name, and file type.

        Args:
            file_path: Absolute path to a file

        Returns:
            (project, run_name, file_type) where file_type is 'metrics', 'wal', or 'meta'
            None if path doesn't match expected pattern
        """
        try:
            relative = file_path.relative_to(self.data_dir)
        except ValueError:
            return None

        parts = relative.parts
        if len(parts) != 2:
            return None

        project = parts[0]
        filename = parts[1]

        if filename.endswith(".wal.jsonl"):
            return (project, filename[:-10], "wal")
        elif filename.endswith(".meta.json"):
            return (project, filename[:-10], "meta")
        elif filename.endswith(".jsonl"):
            return (project, filename[:-6], "metrics")

        return None

    def _parse_metric_line(self, line: str, project: str, run: str, since: datetime) -> MetricRecord | None:
        """Parse a JSONL line and return MetricRecord if it passes the since filter.

        Args:
            line: A single line from a JSONL file
            project: Project name
            run: Run name
            since: Filter timestamp - only records with timestamp >= since are returned

        Returns:
            MetricRecord if parsing succeeds and passes filter, None otherwise
        """
        if not line.strip():
            return None
        try:
            entry = json.loads(line)
            ts_value = entry.get("timestamp")
            record_ts = None
            if ts_value is not None:
                with contextlib.suppress(ValueError):
                    record_ts = parse_to_datetime(ts_value)
            if record_ts is None or record_ts >= since:
                entry["run"] = run
                entry["project"] = project
                return MetricRecord(**entry)
        except Exception as e:
            logger.debug(f"[Watcher] Error parsing line: {e}")
        return None

    def _read_file_with_strategy(self, file_path: Path) -> tuple[str, int]:
        """Read file content with size-based strategy.

        For large files, only the tail portion is read to improve initial load time.

        Args:
            file_path: Path to the file to read

        Returns:
            Tuple of (content, end_position) where end_position is the file position after reading
        """
        file_size = file_path.stat().st_size

        if file_size < self.LARGE_FILE_THRESHOLD:
            with open(file_path) as f:
                content = f.read()
                return content, f.tell()

        # Large file: read tail only
        logger.debug(f"[Watcher] Large file ({file_size} bytes), reading tail: {file_path}")
        with open(file_path) as f:
            read_start = max(0, file_size - self.TAIL_READ_SIZE)
            f.seek(read_start)
            content = f.read()
            end_pos = f.tell()

            # Skip partial first line if we didn't start at beginning
            if read_start > 0:
                first_newline = content.find("\n")
                if first_newline != -1:
                    content = content[first_newline + 1 :]

            return content, end_pos

    def _init_run_status(self, project: str, run: str, meta_file: Path) -> None:
        """Initialize run status tracking from meta file.

        Args:
            project: Project name
            run: Run name
            meta_file: Path to the metadata file
        """
        key = (project, run)
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    meta = json.load(f)
                    self._run_statuses[key] = meta.get("status")
            except Exception:
                self._run_statuses[key] = None
        else:
            self._run_statuses[key] = None

    def _matches_targets(self, targets: Mapping[str, list[str] | None], project: str, run: str) -> bool:
        """Check if a project/run matches the subscription targets.

        Args:
            targets: Subscription targets
            project: Project name
            run: Run name

        Returns:
            True if the project/run matches the targets
        """
        if project not in targets:
            return False

        run_list = targets[project]
        if run_list is None:
            # None means watch all runs in the project
            return True

        return run in run_list

    async def _read_initial_data(
        self,
        targets: Mapping[str, list[str] | None],
        since: datetime,
    ) -> AsyncGenerator[MetricRecord | StatusRecord, None]:
        """Read initial data from existing files.

        Args:
            targets: Dictionary mapping project names to run lists
            since: Filter to only yield records with timestamp >= since

        Yields:
            MetricRecord objects from existing files
        """
        for project, run_names in targets.items():
            try:
                validate_name(project, "project name")
            except ValueError as e:
                logger.warning(f"[Watcher] Invalid project name {project}: {e}")
                continue

            project_dir = self.data_dir / project
            if not project_dir.exists():
                logger.warning(f"[Watcher] Project directory does not exist: {project_dir}")
                continue

            # If run_names is None, discover all runs
            if run_names is None:
                actual_runs = []
                for f in project_dir.glob("*.jsonl"):
                    if f.name.endswith(".wal.jsonl"):
                        continue
                    # Skip symlinks to prevent symlink-based attacks
                    if f.is_symlink():
                        logger.warning(f"[Watcher] Skipping symlink: {f}")
                        continue
                    actual_runs.append(f.stem)
                run_names = actual_runs

            for run in run_names:
                # Check which files exist for this run
                wal_file = project_dir / f"{run}.wal.jsonl"
                jsonl_file = project_dir / f"{run}.jsonl"
                meta_file = project_dir / f"{run}.meta.json"

                # Initialize status tracking
                self._init_run_status(project, run, meta_file)

                # Read metrics files
                for file_path in [wal_file, jsonl_file]:
                    if not file_path.exists():
                        continue

                    resolved = file_path.resolve()

                    try:
                        content, end_pos = self._read_file_with_strategy(resolved)
                        self._file_sizes[resolved] = end_pos

                        for line in content.splitlines():
                            record = self._parse_metric_line(line, project, run, since)
                            if record is not None:
                                yield record
                    except Exception as e:
                        logger.warning(f"[Watcher] Error reading {resolved}: {e}")
                        if resolved.exists():
                            self._file_sizes[resolved] = resolved.stat().st_size

                # Record meta file size
                if meta_file.exists():
                    self._file_sizes[meta_file.resolve()] = meta_file.stat().st_size

    async def _dispatch_loop(self) -> None:
        """Main loop: watch data_dir and dispatch to subscribers."""
        logger.info(f"[Watcher] Starting dispatch loop for {self.data_dir}")
        watcher = None

        try:
            watcher = awatch(str(self.data_dir))
            loop_count = 0
            async for changes in watcher:
                loop_count += 1
                if loop_count % 10000 == 0:
                    logger.warning(f"[Watcher] Loop count: {loop_count}, changes: {len(changes)}")
                logger.debug(f"[Watcher] Received {len(changes)} change(s)")

                for _change_type, changed_path_str in changes:
                    changed_path = Path(changed_path_str).resolve()

                    # Parse file path to get project/run/type
                    parsed = self._parse_file_path(changed_path)
                    if parsed is None:
                        continue

                    project, run, file_type = parsed
                    logger.debug(f"[Watcher] File change: {changed_path} (project={project}, run={run}, type={file_type})")

                    # Dispatch to matching subscribers
                    async with self._instance_lock:
                        for sub in self._subscriptions.values():
                            if not self._matches_targets(sub.targets, project, run):
                                continue

                            try:
                                if file_type == "meta":
                                    # Handle metadata/status update
                                    status_record = await self._process_meta_change(changed_path, project, run)
                                    if status_record:
                                        await sub.queue.put(status_record)
                                else:
                                    # Handle metrics update
                                    metric_records = await self._process_metrics_change(changed_path, project, run, sub.since)
                                    for metric_record in metric_records:
                                        await sub.queue.put(metric_record)
                            except Exception as e:
                                logger.error(f"[Watcher] Error dispatching to subscription: {e}")

        except asyncio.CancelledError:
            logger.info("[Watcher] Dispatch loop cancelled")
            raise
        except Exception as e:
            logger.error(f"[Watcher] Error in dispatch loop: {e}")
        finally:
            if watcher is not None:
                logger.info("[Watcher] Closing awatch instance")
                try:
                    await asyncio.wait_for(watcher.aclose(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("[Watcher] Timeout closing awatch instance")
                except Exception as e:
                    logger.error(f"[Watcher] Error closing watcher: {e}")

    async def _process_meta_change(self, file_path: Path, project: str, run: str) -> StatusRecord | None:
        """Process a metadata file change.

        Args:
            file_path: Path to the metadata file
            project: Project name
            run: Run name

        Returns:
            StatusRecord if status changed, None otherwise
        """
        try:
            with open(file_path) as f:
                meta = json.load(f)
                new_status = meta.get("status")

                key = (project, run)
                if new_status != self._run_statuses.get(key):
                    logger.info(f"[Watcher] Status change for {project}/{run}: {self._run_statuses.get(key)} -> {new_status}")
                    self._run_statuses[key] = new_status

                    return StatusRecord(
                        run=run,
                        project=project,
                        status=new_status or RunStatus.WIP.value,
                        is_finished=meta.get("is_finished", False),
                        exit_code=meta.get("exit_code"),
                    )
        except Exception as e:
            logger.error(f"[Watcher] Error reading metadata file {file_path}: {e}")

        return None

    async def _process_metrics_change(self, file_path: Path, project: str, run: str, since: datetime) -> list[MetricRecord]:
        """Process a metrics file change.

        Args:
            file_path: Path to the metrics file
            project: Project name
            run: Run name
            since: Filter timestamp

        Returns:
            List of MetricRecord objects
        """
        records: list[MetricRecord] = []

        try:
            current_size = self._file_sizes.get(file_path, 0)
            with open(file_path) as f:
                f.seek(current_size)
                new_content = f.read()
                self._file_sizes[file_path] = f.tell()

            for line in new_content.splitlines():
                record = self._parse_metric_line(line, project, run, since)
                if record is not None:
                    records.append(record)

        except Exception as e:
            logger.error(f"[Watcher] Error processing metrics file {file_path}: {e}")

        return records

    async def subscribe(
        self,
        targets: Mapping[str, list[str] | None],
        since: datetime,
    ) -> AsyncGenerator[MetricRecord | StatusRecord, None]:
        """Subscribe to file changes for specified targets.

        Args:
            targets: Dictionary mapping project names to list of run names.
                     If run list is None, all runs in the project are watched.
            since: Filter to only yield records with timestamp >= since

        Yields:
            MetricRecord or StatusRecord as files are updated
        """
        # Ensure since is timezone-aware
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        subscription_id = str(uuid.uuid4())
        queue: asyncio.Queue[MetricRecord | StatusRecord | None] = asyncio.Queue()

        subscription = Subscription(
            id=subscription_id,
            targets=targets,
            since=since,
            queue=queue,
        )

        logger.info(f"[Watcher] New subscription {subscription_id} for targets={targets}")

        async with self._instance_lock:
            self._subscriptions[subscription_id] = subscription
            # Start watcher task if not running
            if self._task is None or self._task.done():
                logger.info("[Watcher] Starting dispatch task")
                self._task = asyncio.create_task(self._dispatch_loop())

        try:
            # Yield initial data (existing records >= since)
            async for record in self._read_initial_data(targets, since):
                yield record

            # Yield updates from queue
            while True:
                queued_record: MetricRecord | StatusRecord | None = await queue.get()
                if queued_record is None:  # Sentinel for unsubscribe
                    break
                yield queued_record
        finally:
            await self._unsubscribe(subscription_id)

    async def _unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from file changes.

        Args:
            subscription_id: Subscription ID to remove
        """
        logger.info(f"[Watcher] Unsubscribing {subscription_id}")

        async with self._instance_lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]

            # Stop watcher task if no more subscribers
            if not self._subscriptions and self._task is not None:
                logger.info("[Watcher] No more subscribers, stopping dispatch task")
                self._task.cancel()
                try:
                    await asyncio.wait_for(self._task, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("[Watcher] Timeout waiting for dispatch task to finish")
                except asyncio.CancelledError:
                    pass
                self._task = None

    @property
    def subscription_count(self) -> int:
        """Get the number of active subscriptions."""
        return len(self._subscriptions)
