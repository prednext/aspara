"""
Server-Sent Events (SSE) routes for Aspara Dashboard.

This module handles real-time streaming endpoints:
- Multiple runs metrics streaming
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from aspara.config import (
    get_sse_heartbeat_interval,
    get_sse_send_timeout,
    is_dev_mode,
)
from aspara.models import MetricRecord, StatusRecord

from ..dependencies import RunCatalogDep, ValidatedProject
from ..utils import parse_and_validate_run_list

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/projects/{project}/runs/stream")
async def stream_multiple_runs(
    project: ValidatedProject,
    run_catalog: RunCatalogDep,
    runs: str,
    since: int = Query(
        ...,
        description="Filter metrics since this UNIX timestamp in milliseconds",
    ),
) -> EventSourceResponse:
    """Stream metrics for multiple runs using Server-Sent Events (SSE).

    Args:
        project: Project name.
        runs: Comma-separated list of run names (e.g., "run1,run2,run3").
        since: Filter to only stream metrics with timestamp >= since (required, UNIX ms).

    Returns:
        EventSourceResponse streaming metric and status events from all specified runs.
        Event types:
        - `metric`: `{"event": "metric", "data": <MetricRecord JSON>}`
        - `status`: `{"event": "status", "data": <StatusRecord JSON>}`

    Raises:
        HTTPException: 400 if project/run name is invalid, 422 if since is missing.
    """
    logger.info(f"[SSE ENDPOINT] Called with project={project}, runs={runs}")

    from ..main import app_state

    try:
        run_list = parse_and_validate_run_list(runs)
    except ValueError as e:

        async def validation_error_generator(msg: str = str(e)):
            yield {"event": "error", "data": msg}

        return EventSourceResponse(validation_error_generator())

    # Convert UNIX ms to datetime
    since_dt = datetime.fromtimestamp(since / 1000, tz=timezone.utc)

    async def event_generator():
        logger.info(f"[SSE] event_generator started for project={project}, runs={run_list}")

        # Register current task for dev mode forced cancellation
        current_task = asyncio.current_task()
        if current_task is not None:
            app_state.active_sse_tasks.add(current_task)

        # Create shutdown queue for this connection
        shutdown_queue: asyncio.Queue[None] = asyncio.Queue()
        app_state.active_sse_connections.add(shutdown_queue)

        # Use new subscribe() method with singleton watcher
        targets = {project: run_list}
        metrics_iterator = run_catalog.subscribe(targets, since=since_dt).__aiter__()
        logger.info("[SSE] Created metrics_iterator using subscribe()")

        # In dev mode, use shorter timeout for faster shutdown detection
        dev_mode = is_dev_mode()
        wait_timeout = 1.0 if dev_mode else None

        # Track pending metric task to avoid re-creating it after timeout
        # IMPORTANT: Cancelling a task that's awaiting inside an async generator
        # will close the generator. We must NOT cancel metric_task on timeout.
        pending_metric_task: asyncio.Task[MetricRecord | StatusRecord] | None = None

        try:
            while True:
                # Check shutdown flag in dev mode
                if dev_mode and app_state.shutting_down:
                    logger.info("[SSE] Dev mode: shutdown flag detected")
                    # Cancel pending metric_task before exiting
                    if pending_metric_task is not None:
                        pending_metric_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await pending_metric_task
                    break

                # Create metric_task only if we don't have a pending one
                if pending_metric_task is None:
                    metric_coro = cast(
                        "Coroutine[Any, Any, MetricRecord | StatusRecord]",
                        metrics_iterator.__anext__(),
                    )
                    pending_metric_task = asyncio.create_task(metric_coro, name="metric_task")

                # Always create a new shutdown_task
                shutdown_coro = cast("Coroutine[Any, Any, Any]", shutdown_queue.get())
                shutdown_task = asyncio.create_task(shutdown_coro, name="shutdown_task")

                try:
                    done, pending = await asyncio.wait(
                        [pending_metric_task, shutdown_task],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=wait_timeout,
                    )
                except asyncio.CancelledError:
                    # Cancelled by lifespan handler in dev mode
                    logger.info("[SSE] Task cancelled (dev mode shutdown)")
                    pending_metric_task.cancel()
                    shutdown_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await pending_metric_task
                    with suppress(asyncio.CancelledError):
                        await shutdown_task
                    raise

                # Handle timeout (dev mode only)
                if not done:
                    # Timeout occurred - only cancel shutdown_task, NOT metric_task
                    # Cancelling metric_task would close the async generator!
                    shutdown_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await shutdown_task
                    # pending_metric_task is kept and will be reused in next iteration
                    continue

                logger.debug(f"[SSE] asyncio.wait returned: done={[t.get_name() for t in done]}, pending={[t.get_name() for t in pending]}")

                # Cancel pending tasks (but NOT metric_task if it's pending)
                if shutdown_task in pending:
                    shutdown_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await shutdown_task

                # Check which task completed
                if pending_metric_task in done:
                    # Reset so we create a new task in next iteration
                    completed_task = pending_metric_task
                    pending_metric_task = None
                    try:
                        record = completed_task.result()
                        if isinstance(record, MetricRecord):
                            logger.debug(f"[SSE] Sending metric to client: run={record.run}, step={record.step}")
                            yield {"event": "metric", "data": record.model_dump_json()}
                        elif isinstance(record, StatusRecord):
                            logger.info(f"[SSE] Sending status update to client: run={record.run}, status={record.status}")
                            yield {"event": "status", "data": record.model_dump_json()}
                    except StopAsyncIteration:
                        logger.info("[SSE] No more records (StopAsyncIteration)")
                        break
                elif shutdown_task in done:
                    logger.info("[SSE] Shutdown requested")
                    # Cancel metric_task since we're shutting down
                    if pending_metric_task is not None:
                        pending_metric_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await pending_metric_task
                    break

        except asyncio.CancelledError:
            logger.info("[SSE] Generator cancelled")
            raise
        except Exception as e:
            # Log the full exception internally. In production, send a generic
            # message to the client so internal paths, library internals, or
            # other sensitive details are not leaked over the wire. In dev
            # mode, include the exception text for easier debugging.
            logger.error(f"[SSE] Exception in event_generator: {e}", exc_info=True)
            error_data = str(e) if dev_mode else "Internal server error"
            yield {"event": "error", "data": error_data}
        finally:
            # Clean up: remove this connection from active set
            logger.info("[SSE] event_generator finished, cleaning up")
            app_state.active_sse_connections.discard(shutdown_queue)
            if current_task is not None:
                app_state.active_sse_tasks.discard(current_task)
            # Cancel pending metric task if still running
            if pending_metric_task is not None and not pending_metric_task.done():
                pending_metric_task.cancel()
                with suppress(asyncio.CancelledError):
                    await pending_metric_task
            # Close the async generator to trigger watcher unsubscribe
            try:
                await asyncio.wait_for(metrics_iterator.aclose(), timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("[SSE] Timeout closing metrics_iterator")
            except Exception as e:
                logger.warning(f"[SSE] Error closing metrics_iterator: {e}")

    logger.info(f"[SSE ENDPOINT] Returning EventSourceResponse for runs={run_list}")
    return EventSourceResponse(
        event_generator(),
        ping=get_sse_heartbeat_interval(),
        send_timeout=get_sse_send_timeout(),
    )
