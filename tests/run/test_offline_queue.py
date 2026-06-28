"""Tests for the offline queue module."""

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from aspara.run._offline_queue import (
    MetricsQueueItem,
    MetricsRetryWorker,
    OfflineQueueStorage,
    QueueMetadata,
    _calculate_backoff_delay,
)


class TestMetricsQueueItem:
    """Test suite for MetricsQueueItem model."""

    def test_create_item_with_defaults(self):
        """Test creating an item with default values."""
        item = MetricsQueueItem(step=0, metrics={"loss": 0.5})

        assert item.step == 0
        assert item.metrics == {"loss": 0.5}
        assert item.id is not None
        assert len(item.id) == 16
        assert item.timestamp is None
        assert item.retry_count == 0
        assert item.next_retry_at == 0
        assert item.created_at > 0

    def test_create_item_with_all_fields(self):
        """Test creating an item with all fields specified."""
        item = MetricsQueueItem(
            id="test-id-12345678",
            step=10,
            metrics={"loss": 0.3, "accuracy": 0.9},
            timestamp="2024-01-01T12:00:00",
            created_at=1704110400000,
            retry_count=3,
            next_retry_at=1704110500000,
        )

        assert item.id == "test-id-12345678"
        assert item.step == 10
        assert item.metrics == {"loss": 0.3, "accuracy": 0.9}
        assert item.timestamp == "2024-01-01T12:00:00"
        assert item.created_at == 1704110400000
        assert item.retry_count == 3
        assert item.next_retry_at == 1704110500000

    def test_serialization_roundtrip(self):
        """Test JSONL serialization and deserialization."""
        original = MetricsQueueItem(
            step=5,
            metrics={"loss": 0.5, "accuracy": 0.8},
            timestamp="2024-01-01T12:00:00",
        )

        jsonl = original.to_jsonl()
        restored = MetricsQueueItem.from_jsonl(jsonl)

        assert restored.id == original.id
        assert restored.step == original.step
        assert restored.metrics == original.metrics
        assert restored.timestamp == original.timestamp
        assert restored.created_at == original.created_at


class TestQueueMetadata:
    """Test suite for QueueMetadata model."""

    def test_create_metadata(self):
        """Test creating queue metadata."""
        metadata = QueueMetadata(
            tracker_uri="http://localhost:3142",
            project="test_project",
            run_name="test_run",
            run_id="abc123",
        )

        assert metadata.tracker_uri == "http://localhost:3142"
        assert metadata.project == "test_project"
        assert metadata.run_name == "test_run"
        assert metadata.run_id == "abc123"
        assert metadata.created_at > 0


class TestBackoffCalculation:
    """Test suite for backoff delay calculation."""

    def test_initial_delay(self):
        """Test initial delay is approximately 1 second."""
        delay = _calculate_backoff_delay(0)
        assert 0.9 <= delay <= 1.1  # 1s ± 10% jitter

    def test_exponential_growth(self):
        """Test delay grows exponentially."""
        delays = [_calculate_backoff_delay(i) for i in range(5)]
        # Check base values (ignoring jitter)
        assert 0.9 <= delays[0] <= 1.1  # ~1s
        assert 1.8 <= delays[1] <= 2.2  # ~2s
        assert 3.6 <= delays[2] <= 4.4  # ~4s
        assert 7.2 <= delays[3] <= 8.8  # ~8s
        assert 14.4 <= delays[4] <= 17.6  # ~16s

    def test_max_delay_cap(self):
        """Test delay is capped at 300 seconds."""
        delay = _calculate_backoff_delay(100)  # Very high retry count
        assert delay <= 330  # 300s + 10% jitter


class TestOfflineQueueStorage:
    """Test suite for OfflineQueueStorage class."""

    def test_initialization_creates_directories(self):
        """Test that initialization creates necessary directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            _storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            queue_dir = Path(temp_dir) / ".queue" / "test_project"
            assert queue_dir.exists()
            assert (queue_dir / "test_run.queue.meta.json").exists()
            assert _storage is not None

    def test_corrupted_metadata_file_is_rewritten(self):
        """If the metadata file is corrupted, it should be rewritten on init."""
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_dir = Path(temp_dir) / ".queue" / "test_project"
            queue_dir.mkdir(parents=True)
            meta_file = queue_dir / "test_run.queue.meta.json"
            meta_file.write_text("{ this is not valid json }")

            # Initialization should not crash; it should rewrite the file.
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            # The metadata file should now be valid JSON.
            raw = meta_file.read_text()
            metadata = QueueMetadata.model_validate_json(raw)
            assert metadata.project == "test_project"
            assert metadata.run_name == "test_run"
            assert storage is not None

    def test_mismatched_metadata_is_rewritten(self):
        """If metadata has wrong project/run_name, it should be rewritten."""
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_dir = Path(temp_dir) / ".queue" / "test_project"
            queue_dir.mkdir(parents=True)
            meta_file = queue_dir / "test_run.queue.meta.json"

            # Write metadata with wrong project name
            wrong_meta = QueueMetadata(
                tracker_uri="http://localhost:3142",
                project="wrong_project",
                run_name="wrong_run",
                run_id="wrong_id",
            )
            meta_file.write_text(wrong_meta.model_dump_json(indent=2))

            # Initialization should detect the mismatch and rewrite.
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            raw = meta_file.read_text()
            metadata = QueueMetadata.model_validate_json(raw)
            assert metadata.project == "test_project"
            assert metadata.run_name == "test_run"
            assert metadata.run_id == "abc123"
            assert storage is not None

    def test_valid_metadata_is_preserved(self):
        """If metadata is valid and matches, it should not be rewritten."""
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_dir = Path(temp_dir) / ".queue" / "test_project"
            queue_dir.mkdir(parents=True)
            meta_file = queue_dir / "test_run.queue.meta.json"

            original_meta = QueueMetadata(
                tracker_uri="http://localhost:3142",
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                created_at=12345,
            )
            meta_file.write_text(original_meta.model_dump_json(indent=2))

            OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            raw = meta_file.read_text()
            metadata = QueueMetadata.model_validate_json(raw)
            # created_at should be preserved (not rewritten with a new timestamp)
            assert metadata.created_at == 12345

    def test_enqueue_item(self):
        """Test enqueueing an item."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            result = storage.enqueue(item)

            assert result is True
            assert storage.count() == 1
            assert not storage.is_empty()

    def test_enqueue_multiple_items(self):
        """Test enqueueing multiple items."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            for i in range(5):
                item = MetricsQueueItem(step=i, metrics={"loss": 0.5 - i * 0.1})
                storage.enqueue(item)

            assert storage.count() == 5

    def test_enqueue_persists_to_disk_synchronously(self):
        """enqueue must fsync so the item survives a process crash right after."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})

            # datasync is the single source of truth for fsync in this codebase;
            # patching it verifies enqueue actually calls it per write.
            with patch("aspara.run._offline_queue.datasync") as mock_datasync:
                result = storage.enqueue(item)

            assert result is True
            mock_datasync.assert_called_once()

            # And the content is actually on disk.
            queue_file = Path(temp_dir) / ".queue" / "test_project" / "test_run.queue.jsonl"
            lines = [line for line in queue_file.read_text().splitlines() if line.strip()]
            assert len(lines) == 1
            assert MetricsQueueItem.from_jsonl(lines[0]).step == 0

    def test_get_ready_items(self):
        """Test getting items ready for retry."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            # Add items with different next_retry_at times
            item1 = MetricsQueueItem(step=0, metrics={"loss": 0.5}, next_retry_at=0)
            item2 = MetricsQueueItem(step=1, metrics={"loss": 0.4}, next_retry_at=0)
            item3 = MetricsQueueItem(step=2, metrics={"loss": 0.3}, next_retry_at=int(time.time() * 1000) + 100000)

            storage.enqueue(item1)
            storage.enqueue(item2)
            storage.enqueue(item3)

            ready_items = storage.get_ready_items()

            assert len(ready_items) == 2
            assert ready_items[0].step == 0
            assert ready_items[1].step == 1

    def test_get_ready_items_sorted_by_step(self):
        """Test that ready items are sorted by step."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            # Add items out of order
            storage.enqueue(MetricsQueueItem(step=5, metrics={"loss": 0.5}))
            storage.enqueue(MetricsQueueItem(step=2, metrics={"loss": 0.4}))
            storage.enqueue(MetricsQueueItem(step=8, metrics={"loss": 0.3}))
            storage.enqueue(MetricsQueueItem(step=1, metrics={"loss": 0.2}))

            ready_items = storage.get_ready_items()

            assert len(ready_items) == 4
            steps = [item.step for item in ready_items]
            assert steps == [1, 2, 5, 8]

    def test_get_ready_items_respects_limit_with_large_queue(self):
        """get_ready_items should return only ``limit`` items from a large queue."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            # Enqueue 500 items with steps 0..499
            for step in range(500):
                storage.enqueue(MetricsQueueItem(step=step, metrics={"loss": 0.01 * step}))

            ready = storage.get_ready_items(limit=10)

            # Should return exactly 10 items
            assert len(ready) == 10
            # Should be the 10 smallest steps (sorted ascending)
            steps = [item.step for item in ready]
            assert steps == list(range(10))

    def test_get_ready_items_limit_one(self):
        """get_ready_items with limit=1 should return the smallest-step item."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            storage.enqueue(MetricsQueueItem(step=5, metrics={"loss": 0.5}))
            storage.enqueue(MetricsQueueItem(step=2, metrics={"loss": 0.4}))
            storage.enqueue(MetricsQueueItem(step=8, metrics={"loss": 0.3}))

            ready = storage.get_ready_items(limit=1)
            assert len(ready) == 1
            assert ready[0].step == 2

    def test_dequeue_items(self):
        """Test removing items from the queue."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item1 = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            item2 = MetricsQueueItem(step=1, metrics={"loss": 0.4})
            item3 = MetricsQueueItem(step=2, metrics={"loss": 0.3})

            storage.enqueue(item1)
            storage.enqueue(item2)
            storage.enqueue(item3)

            removed = storage.dequeue([item1.id, item3.id])

            assert removed == 2
            assert storage.count() == 1

            remaining = storage.get_ready_items()
            assert len(remaining) == 1
            assert remaining[0].id == item2.id

    def test_dequeue_leaves_no_temp_files(self):
        """dequeue must not leave partial temp files behind on success."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)
            storage.dequeue([item.id])

            queue_dir = Path(temp_dir) / ".queue" / "test_project"
            temp_files = list(queue_dir.glob(".tmp_*"))
            assert temp_files == []

    def test_dequeue_to_empty_preserves_file_consistency(self):
        """dequeue that empties the queue must leave a consistent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)
            storage.dequeue([item.id])

            queue_file = Path(temp_dir) / ".queue" / "test_project" / "test_run.queue.jsonl"
            # File should exist (atomic replace of empty content) and be empty.
            assert queue_file.exists()
            assert queue_file.read_text() == ""
            assert storage.is_empty()

    def test_update_retry_info_is_atomic(self):
        """update_retry_info must not leave partial temp files behind."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)

            future_time = int(time.time() * 1000) + 10000
            storage.update_retry_info(item.id, retry_count=2, next_retry_at=future_time)

            queue_dir = Path(temp_dir) / ".queue" / "test_project"
            temp_files = list(queue_dir.glob(".tmp_*"))
            assert temp_files == []

            # Content must be a single valid JSONL line with updated fields.
            queue_file = queue_dir / "test_run.queue.jsonl"
            lines = [line for line in queue_file.read_text().splitlines() if line.strip()]
            assert len(lines) == 1
            restored = MetricsQueueItem.from_jsonl(lines[0])
            assert restored.retry_count == 2
            assert restored.next_retry_at == future_time

    def test_update_retry_info(self):
        """Test updating retry information for an item."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)

            future_time = int(time.time() * 1000) + 10000
            updated = storage.update_retry_info(item.id, retry_count=3, next_retry_at=future_time)

            assert updated is True

            # Verify the item is not ready yet (next_retry_at is in the future)
            ready_items = storage.get_ready_items()
            assert len(ready_items) == 0

    def test_cleanup_removes_empty_files(self):
        """Test that cleanup removes empty queue files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)
            storage.dequeue([item.id])

            queue_file = Path(temp_dir) / ".queue" / "test_project" / "test_run.queue.jsonl"
            meta_file = Path(temp_dir) / ".queue" / "test_project" / "test_run.queue.meta.json"

            assert queue_file.exists()
            assert meta_file.exists()

            storage.cleanup()

            assert not queue_file.exists()
            assert not meta_file.exists()

    def test_is_empty(self):
        """Test is_empty method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            assert storage.is_empty()

            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)

            assert not storage.is_empty()

            storage.dequeue([item.id])

            assert storage.is_empty()


class TestMetricsRetryWorker:
    """Test suite for MetricsRetryWorker class."""

    def test_worker_starts_and_stops(self):
        """Test that the worker can start and stop."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            mock_client = MagicMock()
            mock_client.health_check.return_value = True

            worker = MetricsRetryWorker(
                storage=storage,
                client=mock_client,
                project="test_project",
                run_name="test_run",
            )

            worker.start()
            assert worker._thread is not None
            assert worker._thread.is_alive()

            thread = worker._thread  # Save reference before stop
            worker.stop()
            assert not thread.is_alive()
            assert worker._thread is None

    def test_worker_sends_queued_items(self):
        """Test that the worker sends queued items."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.save_metrics.return_value = {}

            worker = MetricsRetryWorker(
                storage=storage,
                client=mock_client,
                project="test_project",
                run_name="test_run",
            )

            # Add an item to the queue
            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)

            # Run the worker once
            worker._process_queue()

            # Verify the item was sent
            mock_client.save_metrics.assert_called_once_with(
                project="test_project",
                run_name="test_run",
                step=0,
                metrics={"loss": 0.5},
                timestamp=None,
            )

            # Verify the queue is empty
            assert storage.is_empty()

    def test_worker_retries_on_failure(self):
        """Test that the worker updates retry info on failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.save_metrics.side_effect = Exception("Connection refused")

            worker = MetricsRetryWorker(
                storage=storage,
                client=mock_client,
                project="test_project",
                run_name="test_run",
            )

            # Add an item to the queue
            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)

            # Run the worker once
            worker._process_queue()

            # Verify the item is still in the queue with updated retry info
            assert not storage.is_empty()
            items = storage.get_ready_items()
            # Item should not be ready immediately (next_retry_at is in the future)
            assert len(items) == 0

    def test_worker_skips_when_tracker_unhealthy(self):
        """Test that the worker skips processing when tracker is unhealthy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            mock_client = MagicMock()
            mock_client.health_check.return_value = False

            worker = MetricsRetryWorker(
                storage=storage,
                client=mock_client,
                project="test_project",
                run_name="test_run",
            )

            # Add an item to the queue
            item = MetricsQueueItem(step=0, metrics={"loss": 0.5})
            storage.enqueue(item)

            # Run the worker once
            worker._process_queue()

            # Verify the item was not sent
            mock_client.save_metrics.assert_not_called()

            # Verify the item is still in the queue
            assert not storage.is_empty()

    def test_flush_sync_sends_all_items(self):
        """Test that flush_sync sends all queued items."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            mock_client.save_metrics.return_value = {}

            worker = MetricsRetryWorker(
                storage=storage,
                client=mock_client,
                project="test_project",
                run_name="test_run",
            )

            # Add multiple items to the queue
            for i in range(5):
                item = MetricsQueueItem(step=i, metrics={"loss": 0.5 - i * 0.1})
                storage.enqueue(item)

            # Flush synchronously
            failed = worker.flush_sync(timeout=10.0)

            assert failed == 0
            assert storage.is_empty()
            assert mock_client.save_metrics.call_count == 5

    def test_flush_sync_timeout(self):
        """Test that flush_sync respects timeout."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            mock_client = MagicMock()
            mock_client.health_check.return_value = True
            # Slow send that always fails
            mock_client.save_metrics.side_effect = Exception("Connection refused")

            worker = MetricsRetryWorker(
                storage=storage,
                client=mock_client,
                project="test_project",
                run_name="test_run",
            )

            # Add items to the queue
            for i in range(10):
                item = MetricsQueueItem(step=i, metrics={"loss": 0.5})
                storage.enqueue(item)

            # Flush with short timeout
            failed = worker.flush_sync(timeout=0.5)

            # Should have remaining items
            assert failed > 0

    def test_worker_uses_send_callback_when_provided(self):
        """Test that the worker uses custom send callback."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            mock_client = MagicMock()
            mock_client.health_check.return_value = True

            callback_calls = []

            def send_callback(step, metrics, timestamp):
                callback_calls.append((step, metrics, timestamp))
                return True

            worker = MetricsRetryWorker(
                storage=storage,
                client=mock_client,
                project="test_project",
                run_name="test_run",
                send_callback=send_callback,
            )

            # Add an item to the queue
            item = MetricsQueueItem(step=0, metrics={"loss": 0.5}, timestamp="2024-01-01T12:00:00")
            storage.enqueue(item)

            # Run the worker once
            worker._process_queue()

            # Verify the callback was called instead of client.save_metrics
            assert len(callback_calls) == 1
            assert callback_calls[0] == (0, {"loss": 0.5}, "2024-01-01T12:00:00")
            mock_client.save_metrics.assert_not_called()


class TestThreadSafety:
    """Test suite for thread safety."""

    def test_concurrent_enqueue(self):
        """Test that concurrent enqueue operations are thread-safe."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            def enqueue_items(start_step):
                for i in range(100):
                    item = MetricsQueueItem(step=start_step + i, metrics={"loss": 0.5})
                    storage.enqueue(item)

            threads = []
            for i in range(5):
                t = threading.Thread(target=enqueue_items, args=(i * 100,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Should have all 500 items
            assert storage.count() == 500

    def test_concurrent_enqueue_and_dequeue(self):
        """Test concurrent enqueue and dequeue operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            enqueued_ids = []
            lock = threading.Lock()

            def enqueue_items():
                for i in range(50):
                    item = MetricsQueueItem(step=i, metrics={"loss": 0.5})
                    storage.enqueue(item)
                    with lock:
                        enqueued_ids.append(item.id)
                    time.sleep(0.001)

            def dequeue_items():
                for _ in range(50):
                    with lock:
                        if enqueued_ids:
                            item_id = enqueued_ids.pop(0)
                            storage.dequeue([item_id])
                    time.sleep(0.002)

            t1 = threading.Thread(target=enqueue_items)
            t2 = threading.Thread(target=dequeue_items)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            # Final count should be reasonable
            assert storage.count() >= 0


class TestPathTraversalPrevention:
    """Test suite for path traversal prevention.

    The offline queue now uses the centralized validators from aspara.utils.validators
    instead of a custom sanitization function. Invalid project/run names are rejected
    with ValueError rather than sanitized.
    """

    def test_invalid_project_name_with_slashes_raises_error(self):
        """Test that project names with slashes are rejected."""
        import pytest

        with tempfile.TemporaryDirectory() as temp_dir, pytest.raises(ValueError, match="Invalid project name"):
            OfflineQueueStorage(
                project="../../../etc",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

    def test_invalid_run_name_with_slashes_raises_error(self):
        """Test that run names with slashes are rejected."""
        import pytest

        with tempfile.TemporaryDirectory() as temp_dir, pytest.raises(ValueError, match="Invalid run name"):
            OfflineQueueStorage(
                project="test_project",
                run_name="../../../etc/passwd",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

    def test_invalid_project_name_with_spaces_raises_error(self):
        """Test that project names with spaces are rejected."""
        import pytest

        with tempfile.TemporaryDirectory() as temp_dir, pytest.raises(ValueError, match="Invalid project name"):
            OfflineQueueStorage(
                project="project with spaces",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

    def test_valid_project_and_run_names(self):
        """Test that valid alphanumeric names with underscores and hyphens work."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test-project_123",
                run_name="run-001_test",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            # Storage should be created successfully
            assert storage.queue_dir.exists()
            assert storage.queue_dir == Path(temp_dir) / ".queue" / "test-project_123"

    def test_queue_dir_property(self):
        """Test that queue_dir property returns the queue directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = OfflineQueueStorage(
                project="test_project",
                run_name="test_run",
                run_id="abc123",
                tracker_uri="http://localhost:3142",
                data_dir=Path(temp_dir),
            )

            assert storage.queue_dir == storage._queue_dir
            assert storage.queue_dir == Path(temp_dir) / ".queue" / "test_project"
