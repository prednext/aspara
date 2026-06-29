"""
HTML page routes for Aspara Dashboard.

This module handles all HTML page rendering endpoints:
- Home page (projects list)
- Project detail page
- Runs list page
- Run detail page
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from starlette.requests import Request

from aspara.config import is_read_only
from aspara.exceptions import RunNotFoundError
from aspara.models import RunStatus
from aspara.utils.timestamp import parse_to_ms

from ..dependencies import (
    ProjectCatalogDep,
    RunCatalogDep,
    ValidatedProject,
    ValidatedRun,
)
from ..services.template_service import (
    TemplateService,
    create_breadcrumbs,
    render_mustache_response,
)

router = APIRouter()


def _format_duration_ms(duration_ms: float | int | None) -> str:
    """Format a duration given in milliseconds into a human-readable string.

    Returns ``"N/A"`` when no duration is available.
    """
    if duration_ms is None or duration_ms < 0:
        return "N/A"
    seconds = duration_ms / 1000.0
    if seconds < 1:
        return f"{int(duration_ms)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    if hours < 24:
        return f"{hours}h {mins}m"
    days = hours // 24
    hrs = hours % 24
    return f"{days}d {hrs}h"


@router.get("/")
async def home(
    request: Request,
    project_catalog: ProjectCatalogDep,
) -> HTMLResponse:
    """Render the projects list page."""
    # Read-only catalog calls: offload to worker threads so the event
    # loop is not blocked on file I/O. Write paths stay synchronous to
    # avoid read-modify-write races (see api_routes.get_project_metadata_api).
    projects = await asyncio.to_thread(project_catalog.get_projects)

    # Format projects for template, including metadata tags.
    # Fetch each project's metadata in parallel via gather.
    metadatas = await asyncio.gather(
        *(asyncio.to_thread(project_catalog.get_metadata, p.name) for p in projects)
    )
    formatted_projects = []
    for project, metadata in zip(projects, metadatas, strict=True):
        tags = metadata.get("tags") or []
        formatted_projects.append(TemplateService.format_project_for_template(project, tags))

    from aspara.config import get_project_search_mode

    project_search_mode = get_project_search_mode()

    context = {
        "page_title": "Aspara",
        "breadcrumbs": create_breadcrumbs([{"label": "Home", "is_home": True}]),
        "projects": formatted_projects,
        "has_projects": len(formatted_projects) > 0,
        "project_search_mode": project_search_mode,
        "read_only": is_read_only(),
    }

    html = render_mustache_response("projects_list", context)
    return HTMLResponse(content=html)


@router.get("/projects/{project}")
async def project_detail(
    request: Request,
    project: ValidatedProject,
    project_catalog: ProjectCatalogDep,
    run_catalog: RunCatalogDep,
) -> HTMLResponse:
    """Project detail page - shows metrics charts."""
    # Check if project exists
    if not await asyncio.to_thread(project_catalog.exists, project):
        raise HTTPException(status_code=404, detail=f"Project '{project}' not found")

    runs = await asyncio.to_thread(run_catalog.get_runs, project)

    # Format runs for template (excluding corrupted runs)
    formatted_runs = []
    for run in runs:
        formatted = TemplateService.format_run_for_project_detail(run)
        if formatted is not None:
            formatted_runs.append(formatted)

    # Find the most recent last_update from all runs
    project_last_update = None
    if runs:
        last_updates = [r.last_update for r in runs if r.last_update is not None]
        if last_updates:
            project_last_update = max(last_updates)

    context = {
        "page_title": f"{project} - Metrics",
        "breadcrumbs": create_breadcrumbs([
            {"label": "Home", "url": "/", "is_home": True},
            {"label": project},
        ]),
        "project": project,
        "runs": formatted_runs,
        "has_runs": len(formatted_runs) > 0,
        "run_count": len(formatted_runs),
        "formatted_project_last_update": (project_last_update.strftime("%b %d, %Y at %I:%M %p") if project_last_update else "N/A"),
        "read_only": is_read_only(),
    }

    html = render_mustache_response("project_detail", context)
    return HTMLResponse(content=html)


@router.get("/projects/{project}/runs")
async def list_project_runs(
    request: Request,
    project: ValidatedProject,
    project_catalog: ProjectCatalogDep,
    run_catalog: RunCatalogDep,
) -> HTMLResponse:
    """List runs in a project."""
    # Check if project exists
    if not await asyncio.to_thread(project_catalog.exists, project):
        raise HTTPException(status_code=404, detail=f"Project '{project}' not found")

    runs = await asyncio.to_thread(run_catalog.get_runs, project)

    # Format runs for template
    formatted_runs = [TemplateService.format_run_for_list(run) for run in runs]

    context = {
        "page_title": f"{project} - Runs",
        "breadcrumbs": create_breadcrumbs([
            {"label": "Home", "url": "/", "is_home": True},
            {"label": project, "url": f"/projects/{project}"},
            {"label": "Runs"},
        ]),
        "project": project,
        "runs": formatted_runs,
        "has_runs": len(formatted_runs) > 0,
        "read_only": is_read_only(),
    }

    html = render_mustache_response("runs_list", context)
    return HTMLResponse(content=html)


@router.get("/projects/{project}/runs/{run}")
async def get_run(
    request: Request,
    project: ValidatedProject,
    run: ValidatedRun,
    project_catalog: ProjectCatalogDep,
    run_catalog: RunCatalogDep,
) -> HTMLResponse:
    """Get run details including parameters and metrics."""
    # Check if project exists
    if not await asyncio.to_thread(project_catalog.exists, project):
        raise HTTPException(status_code=404, detail=f"Project '{project}' not found")

    # Get Run information and check if it's corrupted
    try:
        current_run = await asyncio.to_thread(run_catalog.get, project, run)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found in project '{project}'") from e

    is_corrupted = current_run.is_corrupted
    error_message = current_run.error_message
    run_tags = current_run.tags

    # Load metrics, artifacts, and metadata in parallel
    df_metrics, artifacts, metadata = await asyncio.gather(
        asyncio.to_thread(run_catalog.load_metrics, project, run),
        run_catalog.get_artifacts_async(project, run),
        run_catalog.get_run_config_async(project, run),
    )

    # Extract params from metadata
    params: dict[str, Any] = {}
    params.update(metadata.get("params", {}))
    params.update(metadata.get("config", {}))

    # Format data for template
    formatted_params = [{"key": k, "value": v} for k, v in params.items()]

    # Get latest metrics for scalar display from wide-format DataFrame
    latest_metrics: dict[str, Any] = {}
    if len(df_metrics) > 0:
        # Get last row (latest metrics)
        last_row = df_metrics.tail(1).to_dicts()[0]
        # Extract metric columns (those starting with underscore)
        for col, value in last_row.items():
            if col.startswith("_") and value is not None:
                # Remove underscore prefix
                metric_name = col[1:]
                latest_metrics[metric_name] = value

    formatted_latest_metrics = [{"key": k, "value": f"{v:.4f}" if isinstance(v, int | float) else str(v)} for k, v in latest_metrics.items()]

    # Resolve start/finish timestamps (in ms) from metadata. The metadata may
    # store them as either UNIX milliseconds (real API) or ISO 8601 strings
    # (legacy/test fixtures), so normalize via parse_to_ms.
    start_time_raw = metadata.get("start_time")
    finish_time_raw = metadata.get("finish_time")
    start_time_ms: int | None = None
    finish_time_ms: int | None = None
    if start_time_raw is not None:
        try:
            start_time_ms = parse_to_ms(start_time_raw)
        except ValueError:
            start_time_ms = None
    if finish_time_raw is not None:
        try:
            finish_time_ms = parse_to_ms(finish_time_raw)
        except ValueError:
            finish_time_ms = None

    # Compute duration. For WIP runs (no finish_time), use the most recent
    # metrics timestamp as the current end so the user sees elapsed time.
    duration_ms: int | None = None
    if start_time_ms is not None:
        end_ms: int | None = finish_time_ms
        if end_ms is None and len(df_metrics) > 0 and "timestamp" in df_metrics.columns:
            last_ts = df_metrics.select("timestamp").to_series().max()
            if isinstance(last_ts, datetime):
                end_ms = int(last_ts.timestamp() * 1000)
            elif isinstance(last_ts, (int, float)):
                end_ms = int(last_ts)
        if end_ms is not None:
            duration_ms = end_ms - start_time_ms

    if duration_ms is not None:
        formatted_duration = _format_duration_ms(duration_ms)
    elif not is_corrupted and current_run.status == RunStatus.WIP:
        # WIP run with no metrics yet.
        formatted_duration = "Running..."
    else:
        formatted_duration = "N/A"

    # Step count = number of logged metric rows
    step_count = len(df_metrics)

    # Start time display: prefer metadata start_time, fall back to DataFrame
    start_time_display = "N/A"
    if start_time_ms is not None:
        try:
            from aspara.utils.timestamp import parse_to_datetime

            start_time_display = parse_to_datetime(start_time_ms).strftime("%B %d, %Y at %I:%M %p")
        except ValueError:
            start_time_display = "N/A"
    elif len(df_metrics) > 0 and "timestamp" in df_metrics.columns:
        ts = df_metrics.select("timestamp").to_series().min()
        if isinstance(ts, datetime):
            start_time_display = ts.strftime("%B %d, %Y at %I:%M %p")

    # Run status flags for template rendering
    status = current_run.status
    status_value = status.value

    context = {
        "page_title": f"{run} - Details",
        "breadcrumbs": create_breadcrumbs([
            {"label": "Home", "url": "/", "is_home": True},
            {"label": project, "url": f"/projects/{project}"},
            {"label": "Runs", "url": f"/projects/{project}/runs"},
            {"label": run},
        ]),
        "project": project,
        "run_name": run,
        "params": formatted_params,
        "has_params": len(formatted_params) > 0,
        "latest_metrics": formatted_latest_metrics,
        "has_latest_metrics": len(formatted_latest_metrics) > 0,
        "formatted_start_time": start_time_display,
        "duration": formatted_duration,
        "step_count": step_count,
        "status": status_value,
        "is_wip": status == RunStatus.WIP,
        "is_completed": status == RunStatus.COMPLETED,
        "is_failed": status == RunStatus.FAILED,
        "is_maybe_failed": status == RunStatus.MAYBE_FAILED,
        "has_tags": len(run_tags) > 0,
        "tags": run_tags,
        "artifacts": [TemplateService.format_artifact_for_template(artifact) for artifact in artifacts],
        "has_artifacts": len(artifacts) > 0,
        "is_corrupted": is_corrupted,
        "error_message": error_message,
        "read_only": is_read_only(),
    }

    html = render_mustache_response("run_detail", context)
    return HTMLResponse(content=html)
