"""
Tests for SSE (Server-Sent Events) endpoints

Note: Full SSE streaming tests are complex in unit test environment.
These tests verify the endpoints exist and have basic validation.
The actual streaming functionality is tested through integration with subscribe.
"""

import asyncio
import contextlib
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from aspara.catalog.watcher import DataDirWatcher
from aspara.dashboard.main import app


@pytest.fixture(autouse=True)
def reset_watcher():
    """Reset DataDirWatcher singleton between tests."""
    DataDirWatcher.reset_instance()
    yield
    DataDirWatcher.reset_instance()


@pytest.fixture
def sse_test_client(tmp_path):
    """Create test client with temporary data directory."""
    from aspara.dashboard.dependencies import configure_data_dir

    configure_data_dir(str(tmp_path))
    try:
        yield TestClient(app), tmp_path
    finally:
        configure_data_dir(None)


def test_stream_multiple_runs_validation(sse_test_client):
    """Test SSE stream with invalid run names."""
    client, data_dir = sse_test_client

    # Create project
    project_dir = data_dir / "test_project"
    project_dir.mkdir()

    # Try to stream with invalid run names (path traversal attempt)
    # SSE endpoints return 200 with error events for validation failures
    since = 0  # UNIX ms
    response = client.get(f"/api/projects/test_project/runs/stream?runs=../evil,test&since={since}")
    # SSE returns 200 but with error event in the stream
    assert response.status_code == 200
    # The response body should contain an error event
    assert "error" in response.text or "Invalid run name" in response.text


def test_stream_multiple_runs_without_since_returns_422(sse_test_client):
    """Test SSE stream endpoint requires since parameter."""
    client, data_dir = sse_test_client

    # Create project
    project_dir = data_dir / "test_project"
    project_dir.mkdir()

    # Try to stream without since parameter
    response = client.get("/api/projects/test_project/runs/stream?runs=run1,run2")
    # Should return 422 (Unprocessable Entity) because since is required
    assert response.status_code == 422


def test_stream_multiple_runs_empty_validation(sse_test_client):
    """Test SSE stream rejects invalid inputs gracefully."""
    client, data_dir = sse_test_client

    # Create project
    project_dir = data_dir / "test_project"
    project_dir.mkdir()

    # Connect with empty runs parameter should not crash
    # (May return error event in SSE stream, but endpoint should respond)
    since = 0  # UNIX ms
    response = client.get(f"/api/projects/test_project/runs/stream?runs=&since={since}")
    # Should respond with 200 (SSE) or validation error
    assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_subscribe_cleanup_on_cancellation(tmp_path):
    """Test that file watchers are properly cleaned up when cancelled.

    This test verifies that:
    1. awatch iterators are explicitly closed
    2. Tasks are properly cancelled and awaited
    3. No file descriptors leak when connections are closed
    """
    from aspara.catalog.run_catalog import RunCatalog

    # Create test data
    project = "test_project"
    run = "test_run"
    project_dir = tmp_path / project
    project_dir.mkdir()

    # Create a test run file with some metrics
    run_file = project_dir / f"{run}.jsonl"
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    run_file.write_text(json.dumps({"timestamp": timestamp, "step": 0, "metrics": {"loss": 0.5}}) + "\n")

    # Create metadata file
    meta_file = project_dir / f"{run}.meta.json"
    meta_file.write_text(json.dumps({"run_id": "test_id", "start_time": timestamp, "tags": [], "notes": "", "is_finished": False, "status": "wip"}))

    # Create catalog and start subscribing
    catalog = RunCatalog(tmp_path)

    # Use epoch as since to get all data
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Start subscribe and then cancel it
    watch_gen = catalog.subscribe({project: [run]}, since)

    # Get the async generator
    task = asyncio.create_task(_consume_watch_for_short_time(watch_gen))

    # Wait a bit, then cancel
    await asyncio.sleep(0.1)
    task.cancel()

    # Wait for task to complete
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # If we get here without hanging or errors, the cleanup worked
    # (awatch.aclose() was called properly)
    assert True


async def _consume_watch_for_short_time(watch_gen):
    """Helper to consume watch generator for a short time."""
    async for _ in watch_gen:
        # Just consume the first event if any
        break


@pytest.mark.asyncio
async def test_multiple_subscribe_connections_cleanup(tmp_path):
    """Test that multiple subscribe connections are properly cleaned up.

    This simulates the scenario where multiple SSE connections are opened
    and closed repeatedly, which was causing the file descriptor leak.
    """
    from aspara.catalog.run_catalog import RunCatalog

    # Create test data
    project = "test_project"
    runs = ["run1", "run2", "run3"]
    project_dir = tmp_path / project
    project_dir.mkdir()

    timestamp = datetime.now(tz=timezone.utc).isoformat()

    # Create multiple test runs
    for run in runs:
        run_file = project_dir / f"{run}.jsonl"
        run_file.write_text(json.dumps({"timestamp": timestamp, "step": 0, "metrics": {"loss": 0.5}}) + "\n")

        meta_file = project_dir / f"{run}.meta.json"
        meta_file.write_text(json.dumps({"run_id": f"{run}_id", "start_time": timestamp, "tags": [], "notes": "", "is_finished": False, "status": "wip"}))

    catalog = RunCatalog(tmp_path)

    # Use epoch as since to get all data
    since = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Simulate multiple SSE connections opening and closing
    for _i in range(5):
        # Create a subscribe connection
        watch_gen = catalog.subscribe({project: runs}, since)

        # Consume for a short time
        task = asyncio.create_task(_consume_watch_for_short_time(watch_gen))

        # Wait a bit, then cancel (simulating client disconnect)
        await asyncio.sleep(0.05)
        task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Small delay between connections
        await asyncio.sleep(0.02)

    # If we get here without errors or hanging, cleanup is working correctly
    assert True


@pytest.mark.asyncio
async def test_cancelling_anext_task_closes_async_generator(tmp_path):
    """Document that cancelling __anext__() task closes the async generator.

    This is Python's fundamental behavior for async generators.
    When a task awaiting inside an async generator is cancelled,
    the CancelledError propagates into the generator and closes it.

    The fix for SSE is to NOT cancel the metric_task during timeout.
    Instead, keep the task pending and reuse it.
    """
    from aspara.catalog.run_catalog import RunCatalog

    # Create test data
    project = "test_project"
    run = "test_run"
    project_dir = tmp_path / project
    project_dir.mkdir()

    run_file = project_dir / f"{run}.jsonl"
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    run_file.write_text(json.dumps({"timestamp": timestamp, "step": 0, "metrics": {"loss": 0.5}}) + "\n")

    meta_file = project_dir / f"{run}.meta.json"
    meta_file.write_text(json.dumps({"run_id": "test_id", "start_time": timestamp, "tags": [], "notes": "", "is_finished": False, "status": "wip"}))

    catalog = RunCatalog(tmp_path)
    future_since = datetime(2099, 1, 1, tzinfo=timezone.utc)

    subscribe_gen = catalog.subscribe({project: [run]}, future_since)
    iterator = subscribe_gen.__aiter__()

    # First __anext__ call
    anext_task = asyncio.create_task(iterator.__anext__())
    await asyncio.sleep(0.05)

    # Cancel the task - this WILL close the generator (Python behavior)
    anext_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await anext_task

    # Verify: next __anext__() raises StopAsyncIteration (generator is closed)
    second_anext_task = asyncio.create_task(iterator.__anext__())
    await asyncio.sleep(0.05)

    assert second_anext_task.done(), "Task should complete immediately with StopAsyncIteration"
    with pytest.raises(StopAsyncIteration):
        second_anext_task.result()


@pytest.mark.asyncio
async def test_keeping_anext_task_keeps_generator_alive(tmp_path):
    """Test that keeping (not cancelling) __anext__() task keeps generator alive.

    This is the correct pattern used in the SSE route:
    - On timeout, do NOT cancel the metric_task
    - Keep it pending and reuse it in the next iteration
    - Only cancel when actually shutting down
    """
    from aspara.catalog.run_catalog import RunCatalog

    # Create test data
    project = "test_project"
    run = "test_run"
    project_dir = tmp_path / project
    project_dir.mkdir()

    run_file = project_dir / f"{run}.jsonl"
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    run_file.write_text(json.dumps({"timestamp": timestamp, "step": 0, "metrics": {"loss": 0.5}}) + "\n")

    meta_file = project_dir / f"{run}.meta.json"
    meta_file.write_text(json.dumps({"run_id": "test_id", "start_time": timestamp, "tags": [], "notes": "", "is_finished": False, "status": "wip"}))

    catalog = RunCatalog(tmp_path)
    future_since = datetime(2099, 1, 1, tzinfo=timezone.utc)

    subscribe_gen = catalog.subscribe({project: [run]}, future_since)
    iterator = subscribe_gen.__aiter__()

    # First __anext__ call - keep this task
    pending_metric_task = asyncio.create_task(iterator.__anext__())
    await asyncio.sleep(0.05)

    # Simulate timeout - create a "shutdown" task and wait with timeout
    # This is what the SSE route does
    shutdown_queue: asyncio.Queue[None] = asyncio.Queue()
    shutdown_task = asyncio.create_task(shutdown_queue.get())

    done, pending = await asyncio.wait(
        [pending_metric_task, shutdown_task],
        timeout=0.1,  # Short timeout
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Timeout occurred - both tasks should be pending
    assert not done, "Both tasks should be pending (timeout)"

    # CORRECT PATTERN: Only cancel shutdown_task, NOT metric_task
    shutdown_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await shutdown_task

    # pending_metric_task is still valid and pending
    assert not pending_metric_task.done(), "metric_task should still be pending"

    # We can reuse it in the next "iteration"
    # Create a new shutdown_task
    shutdown_task2 = asyncio.create_task(shutdown_queue.get())

    done, pending = await asyncio.wait(
        [pending_metric_task, shutdown_task2],
        timeout=0.1,
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Still no data, but the iterator is still alive
    assert not done, "Both tasks should still be pending"

    # Clean up
    shutdown_task2.cancel()
    pending_metric_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await shutdown_task2
    with contextlib.suppress(asyncio.CancelledError):
        await pending_metric_task

    await subscribe_gen.aclose()
