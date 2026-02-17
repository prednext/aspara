"""Offline queue for RemoteRun metrics when tracker is unavailable.

This module provides offline queueing capability for metrics when the tracker
server is temporarily unavailable. Metrics are persisted to disk and retried
with exponential backoff when the server becomes available again.
"""

from __future__ import annotations

import random
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ValidationError

from aspara.config import get_data_dir
from aspara.logger import logger
from aspara.utils.validators import validate_project_name, validate_run_name

if TYPE_CHECKING:
    from aspara.run._remote_run import TrackerClient


class MetricsQueueItem(BaseModel):
    """A single queued metrics item awaiting delivery to the tracker."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    step: int
    metrics: dict[str, Any]
    timestamp: str | None = None
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    retry_count: int = 0
    next_retry_at: int = 0

    def to_jsonl(self) -> str:
        """Serialize to JSONL format."""
        return self.model_dump_json()

    @classmethod
    def from_jsonl(cls, line: str) -> MetricsQueueItem:
        """Deserialize from JSONL format."""
        return cls.model_validate_json(line)


class QueueMetadata(BaseModel):
    """Metadata for a queue file, stored separately."""

    tracker_uri: str
    project: str
    run_name: str
    run_id: str
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))


# Backoff configuration
_BASE_DELAY_SECONDS = 1.0
_MAX_DELAY_SECONDS = 300.0
_JITTER_FACTOR = 0.1

# Resource limits
_MAX_QUEUE_ITEMS = 10_000
_MAX_QUEUE_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Health check cache duration
_HEALTH_CHECK_CACHE_SECONDS = 30


def _calculate_backoff_delay(retry_count: int) -> float:
    """Calculate exponential backoff delay with jitter.

    Args:
        retry_count: Number of retries so far

    Returns:
        Delay in seconds before next retry
    """
    delay = min(_BASE_DELAY_SECONDS * (2**retry_count), _MAX_DELAY_SECONDS)
    jitter = delay * _JITTER_FACTOR * (2 * random.random() - 1)
    return delay + jitter


class OfflineQueueStorage:
    """Manages persistent storage of queued metrics items.

    Queue files are stored at:
        {data_dir}/.queue/{project}/{run_name}.queue.jsonl
        {data_dir}/.queue/{project}/{run_name}.queue.meta.json
    """

    def __init__(
        self,
        project: str,
        run_name: str,
        run_id: str,
        tracker_uri: str,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize queue storage.

        Args:
            project: Project name
            run_name: Run name
            run_id: Run ID
            tracker_uri: Tracker server URI
            data_dir: Base data directory (defaults to get_data_dir())
        """
        self.project = project
        self.run_name = run_name
        self.run_id = run_id
        self.tracker_uri = tracker_uri
        self.data_dir = data_dir or get_data_dir()

        self._lock = threading.Lock()
        self._item_count = 0

        # Validate names to prevent path traversal attacks
        # Using the same validators as the rest of the codebase for consistency
        validate_project_name(project)
        validate_run_name(run_name)

        # Paths (names are now validated, safe to use directly)
        self._queue_dir = self.data_dir / ".queue" / project
        self._queue_file = self._queue_dir / f"{run_name}.queue.jsonl"
        self._meta_file = self._queue_dir / f"{run_name}.queue.meta.json"

        # Initialize directories and metadata
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Ensure queue directory and metadata file exist."""
        self._queue_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata file if it doesn't exist
        if not self._meta_file.exists():
            metadata = QueueMetadata(
                tracker_uri=self.tracker_uri,
                project=self.project,
                run_name=self.run_name,
                run_id=self.run_id,
            )
            self._meta_file.write_text(metadata.model_dump_json(indent=2))

        # Count existing items
        if self._queue_file.exists():
            try:
                with self._queue_file.open("r") as f:
                    self._item_count = sum(1 for line in f if line.strip())
            except OSError:
                self._item_count = 0

    def enqueue(self, item: MetricsQueueItem) -> bool:
        """Add an item to the queue.

        Args:
            item: Queue item to add

        Returns:
            True if item was added, False if queue is full
        """
        with self._lock:
            # Check resource limits
            if self._item_count >= _MAX_QUEUE_ITEMS:
                logger.warning(f"Offline queue full ({_MAX_QUEUE_ITEMS} items). Dropping oldest metrics.")
                self._drop_oldest_items(count=100)

            if self._queue_file.exists():
                file_size = self._queue_file.stat().st_size
                if file_size >= _MAX_QUEUE_FILE_SIZE:
                    logger.warning(f"Offline queue file too large ({file_size / 1024 / 1024:.1f}MB). Dropping oldest metrics.")
                    self._drop_oldest_items(count=100)

            try:
                with self._queue_file.open("a") as f:
                    f.write(item.to_jsonl() + "\n")
                self._item_count += 1
                return True
            except OSError as e:
                logger.warning(f"Failed to write to offline queue: {e}")
                return False

    def _drop_oldest_items(self, count: int) -> None:
        """Drop the oldest items from the queue.

        Must be called with lock held.

        Args:
            count: Number of items to drop
        """
        if not self._queue_file.exists():
            return

        try:
            with self._queue_file.open("r") as f:
                lines = f.readlines()

            remaining = lines[count:]
            with self._queue_file.open("w") as f:
                f.writelines(remaining)

            self._item_count = len(remaining)
        except OSError as e:
            logger.warning(f"Failed to drop oldest items from queue: {e}")

    def get_ready_items(self, limit: int = 100) -> list[MetricsQueueItem]:
        """Get items ready for retry, sorted by step.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of items ready for retry
        """
        now_ms = int(time.time() * 1000)
        items: list[MetricsQueueItem] = []

        with self._lock:
            if not self._queue_file.exists():
                return items

            try:
                with self._queue_file.open("r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            item = MetricsQueueItem.from_jsonl(line.strip())
                            if item.next_retry_at <= now_ms:
                                items.append(item)
                        except (ValueError, ValidationError) as e:
                            logger.debug(f"Skipping invalid queue item: {e}")
                            continue

                        if len(items) >= limit:
                            break
            except OSError:
                pass

        # Sort by step to maintain order
        items.sort(key=lambda x: (x.step, x.created_at))
        return items[:limit]

    def dequeue(self, item_ids: list[str]) -> int:
        """Remove items from the queue by ID.

        Args:
            item_ids: List of item IDs to remove

        Returns:
            Number of items removed
        """
        if not item_ids:
            return 0

        ids_set = set(item_ids)
        removed = 0

        with self._lock:
            if not self._queue_file.exists():
                return 0

            try:
                with self._queue_file.open("r") as f:
                    lines = f.readlines()

                remaining_lines: list[str] = []
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        item = MetricsQueueItem.from_jsonl(line.strip())
                        if item.id in ids_set:
                            removed += 1
                            continue
                    except (ValueError, ValidationError) as e:
                        logger.debug(f"Skipping invalid queue item during dequeue: {e}")
                    remaining_lines.append(line if line.endswith("\n") else line + "\n")

                with self._queue_file.open("w") as f:
                    f.writelines(remaining_lines)

                self._item_count = len(remaining_lines)
            except OSError as e:
                logger.warning(f"Failed to dequeue items: {e}")

        return removed

    def update_retry_info(self, item_id: str, retry_count: int, next_retry_at: int) -> bool:
        """Update retry information for an item.

        Args:
            item_id: ID of the item to update
            retry_count: New retry count
            next_retry_at: Timestamp for next retry (ms)

        Returns:
            True if item was updated, False if not found
        """
        with self._lock:
            if not self._queue_file.exists():
                return False

            try:
                with self._queue_file.open("r") as f:
                    lines = f.readlines()

                updated = False
                new_lines: list[str] = []
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        item = MetricsQueueItem.from_jsonl(line.strip())
                        if item.id == item_id:
                            item.retry_count = retry_count
                            item.next_retry_at = next_retry_at
                            new_lines.append(item.to_jsonl() + "\n")
                            updated = True
                            continue
                    except (ValueError, ValidationError) as e:
                        logger.debug(f"Skipping invalid queue item during retry update: {e}")
                    new_lines.append(line if line.endswith("\n") else line + "\n")

                if updated:
                    with self._queue_file.open("w") as f:
                        f.writelines(new_lines)

                return updated
            except OSError as e:
                logger.warning(f"Failed to update retry info: {e}")
                return False

    @property
    def queue_dir(self) -> Path:
        """Return the queue directory path."""
        return self._queue_dir

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        with self._lock:
            return self._item_count == 0

    def count(self) -> int:
        """Get the number of items in the queue."""
        with self._lock:
            return self._item_count

    def cleanup(self) -> None:
        """Remove queue files if empty."""
        with self._lock:
            if self._item_count == 0:
                try:
                    if self._queue_file.exists():
                        self._queue_file.unlink()
                    if self._meta_file.exists():
                        self._meta_file.unlink()
                    # Try to remove empty directory
                    if self._queue_dir.exists() and not any(self._queue_dir.iterdir()):
                        self._queue_dir.rmdir()
                except OSError:
                    pass


class MetricsRetryWorker:
    """Background worker that retries sending queued metrics.

    The worker periodically checks the queue and attempts to send metrics
    to the tracker. Uses exponential backoff for retries and caches
    health check results to reduce load on the tracker.
    """

    def __init__(
        self,
        storage: OfflineQueueStorage,
        client: TrackerClient,
        project: str,
        run_name: str,
        send_callback: Callable[[int, dict[str, Any], str | None], bool] | None = None,
    ) -> None:
        """Initialize the retry worker.

        Args:
            storage: Queue storage instance
            client: Tracker client for sending metrics
            project: Project name
            run_name: Run name
            send_callback: Optional callback for sending metrics. If provided,
                called instead of client.save_metrics. Signature:
                (step, metrics, timestamp) -> success
        """
        self.storage = storage
        self.client = client
        self.project = project
        self.run_name = run_name
        self._send_callback = send_callback

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._poll_interval = 5.0  # seconds

        # Health check cache
        self._last_health_check: float = 0
        self._last_health_result: bool = False

    def start(self) -> None:
        """Start the background worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.debug("MetricsRetryWorker started")

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background worker thread.

        Args:
            timeout: Maximum time to wait for thread to stop
        """
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.debug("MetricsRetryWorker stopped")

    def _run(self) -> None:
        """Main worker loop."""
        while not self._stop_event.is_set():
            try:
                self._process_queue()
            except Exception as e:
                logger.debug(f"Error in retry worker: {e}")

            # Wait for next poll or stop signal
            self._stop_event.wait(timeout=self._poll_interval)

    def _check_tracker_health(self, force: bool = False) -> bool:
        """Check if the tracker is available.

        Uses cached result if recent enough to reduce load.

        Args:
            force: If True, ignore cache and check immediately

        Returns:
            True if tracker is available
        """
        now = time.time()
        if not force and (now - self._last_health_check) < _HEALTH_CHECK_CACHE_SECONDS:
            return self._last_health_result

        try:
            result = self.client.health_check()
            self._last_health_result = result
            self._last_health_check = now
            return result
        except Exception:
            self._last_health_result = False
            self._last_health_check = now
            return False

    def _mark_unavailable(self) -> None:
        """Mark tracker as unavailable (called on send failure)."""
        self._last_health_result = False
        self._last_health_check = time.time()

    def _mark_available(self) -> None:
        """Mark tracker as available (called on send success)."""
        self._last_health_result = True
        self._last_health_check = time.time()

    def _process_queue(self) -> None:
        """Process ready items from the queue."""
        if self.storage.is_empty():
            return

        if not self._check_tracker_health():
            return

        items = self.storage.get_ready_items(limit=50)
        if not items:
            return

        sent_ids: list[str] = []
        for item in items:
            success = self._send_item(item)
            if success:
                sent_ids.append(item.id)
                logger.info(f"Queued metrics sent successfully (step={item.step})")
            else:
                # Update retry info with backoff
                new_retry_count = item.retry_count + 1
                delay_ms = int(_calculate_backoff_delay(new_retry_count) * 1000)
                next_retry = int(time.time() * 1000) + delay_ms
                self.storage.update_retry_info(item.id, new_retry_count, next_retry)
                logger.debug(f"Retry failed for queued metrics (step={item.step}, retry={new_retry_count}, next_retry_in={delay_ms / 1000:.1f}s)")
                self._mark_unavailable()
                break  # Stop processing on first failure

        if sent_ids:
            self.storage.dequeue(sent_ids)

    def _send_item(self, item: MetricsQueueItem) -> bool:
        """Attempt to send a single item.

        Args:
            item: Queue item to send

        Returns:
            True if sent successfully
        """
        try:
            if self._send_callback is not None:
                return self._send_callback(item.step, item.metrics, item.timestamp)
            else:
                self.client.save_metrics(
                    project=self.project,
                    run_name=self.run_name,
                    step=item.step,
                    metrics=item.metrics,
                    timestamp=item.timestamp,
                )
                self._mark_available()
                return True
        except Exception as e:
            logger.debug(f"Failed to send queued metrics: {e}")
            return False

    def flush_sync(self, timeout: float = 30.0) -> int:
        """Synchronously flush all items in the queue.

        Attempts to send all queued items, blocking until done or timeout.
        Used during finish() to ensure all metrics are sent before exit.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Number of items that failed to send
        """
        start_time = time.time()
        failed_count = 0

        logger.info("Flushing offline queue...")

        while time.time() - start_time < timeout:
            if self.storage.is_empty():
                break

            items = self.storage.get_ready_items(limit=100)
            if not items:
                # All items have future retry times, wait a bit
                time.sleep(0.5)
                continue

            sent_ids: list[str] = []
            for item in items:
                if time.time() - start_time >= timeout:
                    break

                success = self._send_item(item)
                if success:
                    sent_ids.append(item.id)
                else:
                    # On failure, update retry info but continue trying
                    new_retry_count = item.retry_count + 1
                    delay_ms = int(_calculate_backoff_delay(new_retry_count) * 1000)
                    next_retry = int(time.time() * 1000) + delay_ms
                    self.storage.update_retry_info(item.id, new_retry_count, next_retry)

                    # If health check fails, stop trying
                    if not self._check_tracker_health(force=True):
                        break

            if sent_ids:
                self.storage.dequeue(sent_ids)

        # Count remaining items as failed
        failed_count = self.storage.count()
        if failed_count > 0:
            logger.warning(f"Offline queue flush timed out. {failed_count} metrics remain unsent. Queue files preserved at: {self.storage.queue_dir}")
        else:
            # Clean up empty queue files
            self.storage.cleanup()
            logger.info("Offline queue flushed successfully")

        return failed_count
