"""Offline queue for RemoteRun metrics when tracker is unavailable.

This module provides offline queueing capability for metrics when the tracker
server is temporarily unavailable. Metrics are persisted to disk and retried
with exponential backoff when the server becomes available again.
"""

from __future__ import annotations

import heapq
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
from aspara.utils.file import atomic_write_json, atomic_write_text, datasync
from aspara.utils.validators import validate_project_name, validate_run_name

if TYPE_CHECKING:
    from aspara.run._remote_run import TrackerClient


_KIND_RANK = {
    "create": 0,
    "metrics": 1,
    "config": 1,
    "tags": 1,
    "summary": 1,
    "artifact": 1,
    "finish": 2,
}

# create is the only copy of intent, config, and source. finish is the only
# copy of the exit code. A full queue drops older steps instead of these.
_PROTECTED_QUEUE_KINDS = frozenset({"create", "finish"})


class MetricsQueueItem(BaseModel):
    """A single queued item awaiting delivery to the tracker."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    step: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    timestamp: int | str | None = None
    kind: str = "metrics"
    payload: dict[str, Any] = Field(default_factory=dict)
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
        self._shipping_blocked = False
        self._rejected_unsent = 0

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

        # Write metadata file if it doesn't exist, or validate it if it does.
        if not self._meta_file.exists():
            self._write_metadata()
        else:
            self._validate_metadata_file()

        # Count existing items
        if self._queue_file.exists():
            try:
                with self._queue_file.open("r") as f:
                    self._item_count = sum(1 for line in f if line.strip())
            except OSError:
                self._item_count = 0

    def _validate_metadata_file(self) -> None:
        """Load and validate the metadata file.

        If the file is corrupted or has mismatched project/run_name, log a
        warning and overwrite it with correct metadata so the queue can
        continue operating instead of silently ignoring the mismatch.
        """
        try:
            raw = self._meta_file.read_text()
            metadata = QueueMetadata.model_validate_json(raw)
        except (OSError, ValueError, ValidationError) as e:
            logger.warning(f"Queue metadata file is corrupted, rewriting: {e}")
            self._write_metadata()
            return

        # Verify the metadata matches this queue's identity. A mismatch could
        # happen if the queue directory was manually moved or copied.
        if metadata.project != self.project or metadata.run_name != self.run_name:
            logger.warning(
                f"Queue metadata mismatch: file has project={metadata.project!r} "
                f"run_name={metadata.run_name!r}, expected project={self.project!r} "
                f"run_name={self.run_name!r}. Rewriting metadata."
            )
            self._write_metadata()

    def _write_metadata(self) -> None:
        """Write the metadata file with current queue identity.

        Uses atomic write to prevent corruption on crash.
        """
        metadata = QueueMetadata(
            tracker_uri=self.tracker_uri,
            project=self.project,
            run_name=self.run_name,
            run_id=self.run_id,
        )
        atomic_write_json(self._meta_file, metadata.model_dump())

    def enqueue(self, item: MetricsQueueItem) -> bool:
        """Add an item to the queue.

        Args:
            item: Queue item to add

        Returns:
            True if item was added, False if queue is full
        """
        with self._lock:
            if self._shipping_blocked:
                return False
            # Check resource limits. create and finish stay; older steps are dropped.
            if self._item_count >= _MAX_QUEUE_ITEMS:
                logger.warning(f"Offline queue full ({_MAX_QUEUE_ITEMS} items). Dropping oldest metrics.")
                if self._drop_oldest_items(count=100) == 0:
                    logger.warning("Offline queue is full. Keeping the create request and not queueing this item.")
                    return False

            if self._queue_file.exists():
                file_size = self._queue_file.stat().st_size
                if file_size >= _MAX_QUEUE_FILE_SIZE:
                    logger.warning(f"Offline queue file too large ({file_size / 1024 / 1024:.1f}MB). Dropping oldest metrics.")
                    if self._drop_oldest_items(count=100) == 0:
                        logger.warning("Offline queue file is full. Keeping the create request and not queueing this item.")
                        return False

            try:
                self._queue_dir.mkdir(parents=True, exist_ok=True)
                with self._queue_file.open("a") as f:
                    f.write(item.to_jsonl() + "\n")
                    f.flush()
                    datasync(f.fileno())
                self._item_count += 1
                return True
            except OSError as e:
                logger.warning(f"Failed to write to offline queue: {e}")
                return False

    def _drop_oldest_items(self, count: int) -> int:
        """Drop the oldest queued steps.

        ``create`` and ``finish`` stay, even when they are the oldest lines.
        Must be called with lock held.

        Args:
            count: Maximum number of items to drop

        Returns:
            Number of items dropped
        """
        if not self._queue_file.exists() or count <= 0:
            return 0

        try:
            with self._queue_file.open("r") as f:
                lines = f.readlines()

            remaining: list[str] = []
            dropped = 0
            for line in lines:
                if not line.strip():
                    continue
                if dropped < count and not self._is_protected_queue_item(line):
                    dropped += 1
                    continue
                remaining.append(line if line.endswith("\n") else line + "\n")

            if dropped == 0:
                return 0

            atomic_write_text(self._queue_file, lambda f: f.writelines(remaining), suffix=".jsonl")
            self._item_count = len(remaining)
            return dropped
        except OSError as e:
            logger.warning(f"Failed to drop oldest items from queue: {e}")
            return 0

    def _is_protected_queue_item(self, line: str) -> bool:
        item = self._parse_queue_item(line.strip())
        if item is None:
            return False
        return (item.kind or "metrics") in _PROTECTED_QUEUE_KINDS

    @staticmethod
    def _parse_queue_item(line: str) -> MetricsQueueItem | None:
        """Parse a JSONL queue item, logging and returning None on failure."""
        try:
            return MetricsQueueItem.from_jsonl(line)
        except (ValueError, ValidationError) as e:
            logger.debug(f"Skipping invalid queue item: {e}")
            return None

    def get_ready_items(self, limit: int = 100) -> list[MetricsQueueItem]:
        """Get items ready for retry, sorted by step.

        Uses a bounded heap so that at most ``limit`` items are held in
        memory at any time, even if the queue file is very large.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of items ready for retry. ``finish`` is left out while any
            other item is still waiting out its retry delay, so a completed
            state cannot land before that item.
        """
        now_ms = int(time.time() * 1000)
        # Min-heap of (sort_key, item) — we push negative sort keys to use
        # heapq as a max-heap of size ``limit``, then pop all and reverse.
        # This keeps memory usage bounded to ``limit`` items.
        heap: list[tuple[tuple[int, int, int], str, MetricsQueueItem]] = []
        waiting_on_backoff = False

        with self._lock:
            if not self._queue_file.exists():
                return []

            try:
                with self._queue_file.open("r") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        item = self._parse_queue_item(stripped)
                        if item is None:
                            continue

                        if item.next_retry_at > now_ms:
                            if item.kind != "finish":
                                waiting_on_backoff = True
                            continue

                        rank = _KIND_RANK.get(item.kind, 1)
                        sort_key = (rank, item.step, item.created_at)
                        # Use negative key for max-heap behavior: heap[0]
                        # holds the item with the LARGEST original key, so
                        # it gets evicted first when a smaller item arrives.
                        neg_key = (-sort_key[0], -sort_key[1], -sort_key[2])
                        if len(heap) < limit:
                            heapq.heappush(heap, (neg_key, item.id, item))
                        elif neg_key > heap[0][0]:
                            heapq.heapreplace(heap, (neg_key, item.id, item))
            except OSError as e:
                logger.warning(f"Failed to read queue file {self._queue_file}: {e}")

        if waiting_on_backoff:
            heap = [entry for entry in heap if entry[2].kind != "finish"]
            heapq.heapify(heap)

        # Extract items in sorted order (kind rank, then step, then created_at).
        result = [heapq.heappop(heap)[2] for _ in range(len(heap))]
        result.reverse()
        return result

    def has_kind(self, kind: str) -> bool:
        """Return True if the queue still holds an item of ``kind``."""
        with self._lock:
            if not self._queue_file.exists():
                return False
            try:
                with self._queue_file.open("r") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        item = self._parse_queue_item(stripped)
                        if item is not None and item.kind == kind:
                            return True
            except OSError:
                return False
        return False

    def drop_kind(self, kind: str) -> int:
        """Remove every queued item of ``kind``.

        Resume drops a finish left by the previous session. That session
        already ended, and this one enqueues its own finish when it ends.
        """
        with self._lock:
            if not self._queue_file.exists():
                return 0
            try:
                with self._queue_file.open("r") as f:
                    lines = f.readlines()

                remaining_lines: list[str] = []
                removed = 0
                for line in lines:
                    if not line.strip():
                        continue
                    item = self._parse_queue_item(line.strip())
                    if item is not None and item.kind == kind:
                        removed += 1
                        continue
                    remaining_lines.append(line if line.endswith("\n") else line + "\n")

                if removed:
                    atomic_write_text(self._queue_file, lambda f: f.writelines(remaining_lines), suffix=".jsonl")
                    self._item_count = len(remaining_lines)
                return removed
            except OSError as e:
                logger.warning(f"Failed to drop queued {kind} items: {e}")
                return 0

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
                    item = self._parse_queue_item(line.strip())
                    if item is not None and item.id in ids_set:
                        removed += 1
                        continue
                    remaining_lines.append(line if line.endswith("\n") else line + "\n")

                atomic_write_text(self._queue_file, lambda f: f.writelines(remaining_lines), suffix=".jsonl")

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
                    item = self._parse_queue_item(line.strip())
                    if item is not None and item.id == item_id:
                        item.retry_count = retry_count
                        item.next_retry_at = next_retry_at
                        new_lines.append(item.to_jsonl() + "\n")
                        updated = True
                        continue
                    new_lines.append(line if line.endswith("\n") else line + "\n")

                if updated:
                    atomic_write_text(self._queue_file, lambda f: f.writelines(new_lines), suffix=".jsonl")

                return updated
            except OSError as e:
                logger.warning(f"Failed to update retry info: {e}")
                return False

    @property
    def queue_dir(self) -> Path:
        """Return the queue directory path."""
        return self._queue_dir

    def reject_shipping(self, *, count_as_unsent: bool = True) -> int:
        """Drop queued items and refuse later enqueues.

        A create conflict (HTTP 409) is permanent: the items are not retried.
        Returns how many items count as unsent. An empty queue still counts
        as one, because the refused create never entered it.
        ``count_as_unsent=False`` is the same-store response: nothing failed,
        and nothing more is sent.
        """
        with self._lock:
            if self._shipping_blocked:
                return self._rejected_unsent
            self._shipping_blocked = True
            # A 409 on create can happen before that create is queued. Count it
            # as one unsent item so flush() does not look like a clean send.
            self._rejected_unsent = max(self._item_count, 1) if count_as_unsent else 0
            self._item_count = 0
            try:
                if self._queue_file.exists():
                    self._queue_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to drop queue file {self._queue_file}: {e}")
            return self._rejected_unsent

    @property
    def shipping_blocked(self) -> bool:
        """True after a create conflict. Further items are not sent."""
        with self._lock:
            return self._shipping_blocked

    @property
    def rejected_unsent(self) -> int:
        """Items dropped because create was rejected."""
        with self._lock:
            return self._rejected_unsent

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
                except OSError as e:
                    logger.debug(f"Failed to cleanup queue files at {self._queue_dir}: {e}")


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
        send_callback: Callable[[int, dict[str, Any], int | str | None], bool] | None = None,
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
        self._send_lock = threading.Lock()
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
        if self.storage.shipping_blocked or self.storage.is_empty():
            return

        if not self._check_tracker_health():
            return

        # finish() waits on this lock, so a stop request ends the batch after
        # the current item instead of sending the same queue in parallel.
        if not self._send_lock.acquire(blocking=False):
            return
        try:
            while not self._stop_event.is_set():
                if self.storage.shipping_blocked or self.storage.is_empty():
                    return
                items = self.storage.get_ready_items(limit=50)
                if self.storage.has_kind("create"):
                    items = [item for item in items if item.kind == "create"]
                if not items:
                    return
                if not self._send_one(items[0]):
                    return
        finally:
            self._send_lock.release()

    def _send_one(self, item: MetricsQueueItem) -> bool:
        """Send one item and remove it from the queue when the send succeeds.

        Returns False when the caller should stop this batch.
        """
        result = self._send_item(item)
        if result == "conflict":
            self.storage.reject_shipping()
            return False
        if result == "same_store":
            self.storage.reject_shipping(count_as_unsent=False)
            return False
        if result == "ok":
            self.storage.dequeue([item.id])
            logger.info(f"Queued metrics sent successfully (step={item.step})")
            return True
        new_retry_count = item.retry_count + 1
        delay_ms = int(_calculate_backoff_delay(new_retry_count) * 1000)
        next_retry = int(time.time() * 1000) + delay_ms
        self.storage.update_retry_info(item.id, new_retry_count, next_retry)
        logger.debug(f"Retry failed for queued metrics (step={item.step}, retry={new_retry_count}, next_retry_in={delay_ms / 1000:.1f}s)")
        self._mark_unavailable()
        return False

    def _send_item(self, item: MetricsQueueItem) -> str:
        """Attempt to send a single item.

        Args:
            item: Queue item to send

        Returns:
            ``ok`` when the item was sent, ``retry`` when it should be tried
            again, ``conflict`` when create was rejected with HTTP 409,
            ``same_store`` when the Tracker is already this directory.
        """
        try:
            if self._send_callback is not None and item.kind in {"metrics", ""}:
                return "ok" if self._send_callback(item.step, item.metrics, item.timestamp) else "retry"
            result = self._dispatch_item(item)
            if (item.kind or "metrics") == "create" and isinstance(result, dict) and result.get("same_store"):
                logger.info(f"Tracker create for {self.project}/{self.run_name} is the local directory. Not shipping a second copy.")
                return "same_store"
            self._mark_available()
            return "ok"
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            kind = item.kind or "metrics"
            if status == 409 and kind == "create":
                print(f"aspara: Tracker already has '{self.run_name}' with a different id; not sending a copy")
                logger.warning(f"Tracker create returned 409 for {self.project}/{self.run_name}. Not retrying and not shipping further items.")
                return "conflict"
            if status == 409:
                self._mark_available()
                return "ok"
            logger.debug(f"Failed to send queued item kind={item.kind}: {e}")
            return "retry"

    def _dispatch_item(self, item: MetricsQueueItem) -> Any:
        """Send one queued item through TrackerClient."""
        payload = item.payload or {}
        kind = item.kind or "metrics"
        if kind == "create":
            return self.client.create_run(
                name=payload.get("name") or self.run_name,
                project=payload.get("project") or self.project,
                config=payload.get("config"),
                tags=payload.get("tags"),
                notes=payload.get("notes"),
                project_tags=payload.get("project_tags"),
                resume=bool(payload.get("resume")),
                intent=payload.get("intent"),
                source=payload.get("source"),
                run_id=payload.get("run_id"),
                client_data_dir=payload.get("client_data_dir"),
            )
        if kind == "finish":
            self.client.finish_run(self.project, self.run_name, int(payload.get("exit_code", 0)))
            return
        if kind == "config":
            self.client.log_config(self.project, self.run_name, payload.get("config") or {})
            return
        if kind == "tags":
            self.client.update_tags(self.project, self.run_name, list(payload.get("tags") or []))
            return
        if kind == "summary":
            self.client.log_summary(self.project, self.run_name, payload.get("summary") or {})
            return
        if kind == "artifact":
            self.client.log_artifact(
                project=self.project,
                run_name=self.run_name,
                file_path=str(payload.get("file_path") or ""),
                name=payload.get("name"),
                description=payload.get("description"),
                category=payload.get("category"),
            )
            return
        self.client.save_metrics(
            project=self.project,
            run_name=self.run_name,
            step=item.step,
            metrics=item.metrics,
            timestamp=item.timestamp,
        )

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

        if self.storage.shipping_blocked:
            return self.storage.rejected_unsent

        with self._send_lock:
            failed_count = self._flush_holding_lock(start_time, timeout)
        return failed_count

    def _flush_holding_lock(self, start_time: float, timeout: float) -> int:
        """Send queued items. Caller holds ``_send_lock``."""
        while time.time() - start_time < timeout:
            if self.storage.is_empty():
                break

            items = self.storage.get_ready_items(limit=100)
            if self.storage.has_kind("create"):
                items = [item for item in items if item.kind == "create"]
            if not items:
                # All items have future retry times, wait a bit
                time.sleep(0.5)
                continue

            for item in items:
                if time.time() - start_time >= timeout:
                    break

                result = self._send_item(item)
                if result == "conflict":
                    return self.storage.reject_shipping()
                if result == "same_store":
                    self.storage.reject_shipping(count_as_unsent=False)
                    return 0
                if result == "ok":
                    self.storage.dequeue([item.id])
                else:
                    # On failure, update retry info but continue trying
                    new_retry_count = item.retry_count + 1
                    delay_ms = int(_calculate_backoff_delay(new_retry_count) * 1000)
                    next_retry = int(time.time() * 1000) + delay_ms
                    self.storage.update_retry_info(item.id, new_retry_count, next_retry)

                    # If health check fails, stop trying
                    if not self._check_tracker_health(force=True):
                        break

        # Count remaining items as failed
        failed_count = self.storage.count()
        if failed_count > 0:
            logger.warning(f"Offline queue flush timed out. {failed_count} metrics remain unsent. Queue files preserved at: {self.storage.queue_dir}")
        else:
            # Clean up empty queue files
            self.storage.cleanup()
            logger.info("Offline queue flushed successfully")

        return failed_count
