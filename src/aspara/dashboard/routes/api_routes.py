"""
REST API routes for Aspara Dashboard.

This module handles all REST API endpoints:
- Artifacts download API
- Bulk metrics API
- Project/Run metadata APIs
- Delete APIs
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import msgpack
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse

from aspara.config import get_resource_limits, is_read_only
from aspara.exceptions import ProjectNotFoundError, RunNotFoundError
from aspara.utils import validators

from ..dependencies import (
    DataDirDep,
    ProjectCatalogDep,
    RunCatalogDep,
    ValidatedProject,
    ValidatedRun,
)
from ..models.metrics import Metadata, MetadataUpdateRequest
from ..utils.compression import compress_metrics


async def verify_csrf_header(x_requested_with: str | None = Header(None, alias="X-Requested-With")) -> None:
    """CSRF protection via custom header check.

    Verifies that requests include the X-Requested-With header, which cannot be set
    by cross-origin requests without CORS preflight. This prevents CSRF attacks.

    Args:
        x_requested_with: The X-Requested-With header value

    Raises:
        HTTPException: 403 if header is missing
    """
    if x_requested_with is None:
        raise HTTPException(status_code=403, detail="Missing X-Requested-With header")


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/projects/{project}/runs/{run}/artifacts/download")
async def download_artifacts_zip(
    project: ValidatedProject,
    run: ValidatedRun,
    data_dir: DataDirDep,
) -> StreamingResponse:
    """Download all artifacts for a run as a ZIP file.

    Args:
        project: Project name.
        run: Run name.

    Returns:
        StreamingResponse with ZIP file containing all artifacts.
        Filename format: `{project}_{run}_artifacts_{timestamp}.zip`

    Raises:
        HTTPException: 400 if project/run name is invalid or total size exceeds limit,
            404 if no artifacts found.
    """
    # Get the artifacts directory path
    artifacts_dir = data_dir / project / run / "artifacts"

    # Validate path to prevent path traversal
    try:
        validators.validate_safe_path(artifacts_dir, data_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid artifacts directory path: {e}") from None

    artifacts_dir_str = str(artifacts_dir)

    if not os.path.exists(artifacts_dir_str):
        raise HTTPException(status_code=404, detail="No artifacts found for this run")

    # Single-pass: collect file info using scandir (caches stat results)
    artifact_entries: list[tuple[str, str, int]] = []  # (name, path, size)
    total_size = 0

    with os.scandir(artifacts_dir_str) as entries:
        for entry in entries:
            if entry.is_file():
                size = entry.stat().st_size  # Uses cached stat
                artifact_entries.append((entry.name, entry.path, size))
                total_size += size

    if not artifact_entries:
        raise HTTPException(status_code=404, detail="No artifact files found")

    # Check total size
    limits = get_resource_limits()
    if total_size > limits.max_zip_size:
        raise HTTPException(
            status_code=400,
            detail=(f"Total artifacts size ({total_size} bytes) exceeds maximum ZIP size limit ({limits.max_zip_size} bytes)"),
        )

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, file_path, _ in artifact_entries:
            # Add file to zip with just the filename (no directory structure)
            zip_file.write(file_path, filename)

    zip_buffer.seek(0)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{project}_{run}_artifacts_{timestamp}.zip"

    # Return as streaming response
    # Encode filename for Content-Disposition header to prevent header injection
    # Use RFC 5987 encoding for non-ASCII characters
    import urllib.parse

    encoded_filename = urllib.parse.quote(zip_filename, safe="")
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


@router.get("/api/projects/{project}/runs/metrics")
async def runs_metrics_api(
    project: ValidatedProject,
    run_catalog: RunCatalogDep,
    runs: str,
    format: str = "json",
    since: int | None = Query(
        default=None,
        description="Filter metrics since this UNIX timestamp in milliseconds",
    ),
) -> Response:
    """Get metrics for multiple runs in a single request.

    Useful for comparing metrics across runs. Returns data in metric-first structure
    where each metric contains data from all requested runs.

    Args:
        project: Project name.
        runs: Comma-separated list of run names (e.g., "run1,run2,run3").
        format: Response format - "json" (default) or "msgpack".
        since: Optional filter to only return metrics with timestamp >= since (UNIX ms).

    Returns:
        Response with structure: `{"project": str, "metrics": {metric: {run: {...}}}}`
        - For "json" format: JSONResponse
        - For "msgpack" format: Response with application/x-msgpack content type

    Raises:
        HTTPException: 400 if project name is invalid, format is invalid,
            or too many runs specified.
    """
    # Validate format parameter
    if format not in ("json", "msgpack"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format: {format}. Must be 'json' or 'msgpack'",
        )

    if not runs:
        if format == "msgpack":
            raise HTTPException(status_code=400, detail="No runs specified")
        return JSONResponse(content={"error": "No runs specified"})

    run_list = [r.strip() for r in runs.split(",") if r.strip()]
    if not run_list:
        if format == "msgpack":
            raise HTTPException(status_code=400, detail="No valid runs specified")
        return JSONResponse(content={"error": "No valid runs specified"})

    # Validate number of runs
    limits = get_resource_limits()
    if len(run_list) > limits.max_metric_names:  # Reuse max_metric_names limit for runs
        raise HTTPException(
            status_code=400,
            detail=f"Too many runs: {len(run_list)} (max: {limits.max_metric_names})",
        )

    # Validate each run name
    for run_name in run_list:
        try:
            validators.validate_run_name(run_name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

    # Convert since (UNIX ms) to datetime if provided
    # Create timezone-naive datetime (matches DataFrame storage)
    since_dt = datetime.fromtimestamp(since / 1000, tz=timezone.utc).replace(tzinfo=None) if since is not None else None

    # Load and downsample metrics for all runs in parallel
    async def load_and_downsample(
        run_name: str,
    ) -> tuple[str, dict[str, dict[str, list]] | None]:
        """Load and downsample metrics for a single run."""
        try:
            df = await asyncio.to_thread(run_catalog.load_metrics, project, run_name, since_dt)
            return (run_name, compress_metrics(df))
        except Exception as e:
            logger.warning(f"Failed to load metrics for {project}/{run_name}: {e}")
            return (run_name, None)

    # Execute all loads in parallel
    results = await asyncio.gather(*[load_and_downsample(run_name) for run_name in run_list])

    # Build metrics_by_run from results
    metrics_by_run: dict[str, dict[str, dict[str, list]]] = {}
    for run_name, metrics in results:
        if metrics is not None:
            metrics_by_run[run_name] = metrics

    # Reorganize to metric-first structure using defaultdict for O(1) key insertion
    metrics_data: dict[str, dict[str, dict[str, list]]] = defaultdict(dict)
    for run_name, run_metrics in metrics_by_run.items():
        for metric_name, metric_arrays in run_metrics.items():
            metrics_data[metric_name][run_name] = metric_arrays

    response_data = {"project": project, "metrics": metrics_data}

    # Return response based on format
    if format == "msgpack":
        # Serialize to MessagePack
        packed_data = msgpack.packb(response_data, use_single_float=True)
        return Response(content=packed_data, media_type="application/x-msgpack")

    return JSONResponse(content=response_data)


@router.get("/api/projects/{project}/metadata")
async def get_project_metadata_api(
    project: ValidatedProject,
    project_catalog: ProjectCatalogDep,
) -> Metadata:
    """Get project metadata.

    Args:
        project: Project name.

    Returns:
        Metadata object containing project metadata (tags, notes, etc.).

    Raises:
        HTTPException: 400 if project name is invalid.
    """
    # Use ProjectCatalog metadata API (synchronous call inside async endpoint)
    metadata = project_catalog.get_metadata(project)
    return Metadata.model_validate(metadata)


@router.put("/api/projects/{project}/metadata")
async def update_project_metadata_api(
    project: ValidatedProject,
    metadata: MetadataUpdateRequest,
    project_catalog: ProjectCatalogDep,
    _csrf: None = Depends(verify_csrf_header),
) -> Metadata:
    """Update project metadata.

    Args:
        project: Project name.
        metadata: MetadataUpdateRequest containing fields to update.

    Returns:
        Metadata object containing the updated project metadata.

    Raises:
        HTTPException: 400 if project name is invalid.
    """
    if is_read_only():
        existing = project_catalog.get_metadata(project)
        return Metadata.model_validate(existing)

    update_data = metadata.model_dump(exclude_none=True)

    # Use ProjectCatalog metadata API
    updated_metadata = project_catalog.update_metadata(project, update_data)
    return Metadata.model_validate(updated_metadata)


@router.delete("/api/projects/{project}")
async def delete_project(
    project: ValidatedProject,
    project_catalog: ProjectCatalogDep,
    _csrf: None = Depends(verify_csrf_header),
) -> Response:
    """Delete a project and all its runs.

    **Warning**: This operation is irreversible.

    Args:
        project: Project name.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException: 400 if project name is invalid, 403 if permission denied,
            404 if project not found, 500 for unexpected errors.
    """
    if is_read_only():
        return Response(status_code=204)

    try:
        project_catalog.delete(project)
        logger.info(f"Deleted project: {project}")
        return Response(status_code=204)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        logger.warning(f"Permission denied deleting project {project}: {e}")
        raise HTTPException(status_code=403, detail="Permission denied") from e
    except Exception as e:
        logger.error(f"Error deleting project {project}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete project") from e


@router.get("/api/projects/{project}/runs/{run}/metadata")
async def get_run_metadata_api(
    project: ValidatedProject,
    run: ValidatedRun,
    run_catalog: RunCatalogDep,
) -> dict[str, Any]:
    """Get run metadata.

    Args:
        project: Project name.
        run: Run name.

    Returns:
        Dictionary containing run metadata (tags, notes, params, etc.).

    Raises:
        HTTPException: 400 if project/run name is invalid.
    """
    # Use RunCatalog metadata API
    metadata = run_catalog.get_metadata(project, run)
    return metadata


@router.put("/api/projects/{project}/runs/{run}/metadata")
async def update_run_metadata_api(
    project: ValidatedProject,
    run: ValidatedRun,
    metadata: MetadataUpdateRequest,
    run_catalog: RunCatalogDep,
    _csrf: None = Depends(verify_csrf_header),
) -> dict[str, Any]:
    """Update run metadata.

    Args:
        project: Project name.
        run: Run name.
        metadata: MetadataUpdateRequest containing fields to update.

    Returns:
        Dictionary containing the updated run metadata.

    Raises:
        HTTPException: 400 if project/run name is invalid.
    """
    if is_read_only():
        existing = run_catalog.get_metadata(project, run)
        return existing

    update_data = metadata.model_dump(exclude_none=True)

    # Use RunCatalog metadata API
    updated_metadata = run_catalog.update_metadata(project, run, update_data)
    return updated_metadata


@router.delete("/api/projects/{project}/runs/{run}")
async def delete_run(
    project: ValidatedProject,
    run: ValidatedRun,
    run_catalog: RunCatalogDep,
    _csrf: None = Depends(verify_csrf_header),
) -> Response:
    """Delete a run and its artifacts.

    **Warning**: This operation is irreversible.

    Args:
        project: Project name.
        run: Run name.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException: 400 if project/run name is invalid, 403 if permission denied,
            404 if project or run not found, 500 for unexpected errors.
    """
    if is_read_only():
        return Response(status_code=204)

    try:
        run_catalog.delete(project, run)
        logger.info(f"Deleted run: {project}/{run}")
        return Response(status_code=204)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        logger.warning(f"Permission denied deleting run {project}/{run}: {e}")
        raise HTTPException(status_code=403, detail="Permission denied") from e
    except Exception as e:
        logger.error(f"Error deleting run {project}/{run}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete run") from e
