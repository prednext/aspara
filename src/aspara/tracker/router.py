"""Aspara Tracker API router.

RESTful API endpoints using FastAPI APIRouter.
"""

import asyncio
import logging
import os
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, UploadFile

from aspara.config import get_resource_limits, is_read_only
from aspara.models import MetricRecord
from aspara.storage import RunMetadataStorage, create_metrics_storage
from aspara.storage.artifacts import ArtifactTooLargeError, FilesystemArtifactStore
from aspara.storage.metrics.base import MetricsStorage
from aspara.tenancy import (
    resolve_artifact_base_dir,
    resolve_data_dir,
    resolve_libsql_tenant,
    tenant_id_from_headers,
)
from aspara.utils import validators
from aspara.utils.metadata import update_project_metadata_tags

from .models import (
    ArtifactUploadResponse,
    ConfigUpdateRequest,
    FinishRequest,
    HealthResponse,
    MetricsResponse,
    RunCreateRequest,
    RunCreateResponse,
    StatusResponse,
    SummaryUpdateRequest,
    TagsUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _metrics_storage_for_request(request: Request, project_name: str, run_name: str) -> MetricsStorage:
    """Build the metrics storage for the request's tenant.

    The tracker is mounted as its own app (no dashboard middleware), so it reads
    the tenant from the request header directly and resolves it through the shared
    :mod:`aspara.tenancy` registry. A libSQL tenant's metrics are written to its
    libSQL database (unconditionally libSQL, ignoring ASPARA_STORAGE_BACKEND);
    otherwise writes go to the tenant's filesystem data directory as before.
    """
    tenant_id = tenant_id_from_headers(request.headers)
    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        # Lazy import so the optional ``libsql`` dependency is only required here.
        from aspara.storage.metrics.libsql import LibsqlMetricsStorage

        return LibsqlMetricsStorage(
            base_dir=spec.base_dir or "",
            project_name=project_name,
            run_name=run_name,
            database=spec.database,
            auth_token=spec.auth_token,
        )
    data_dir = resolve_data_dir(tenant_id)
    return create_metrics_storage(
        backend=None,
        base_dir=str(data_dir),
        project_name=project_name,
        run_name=run_name,
    )


def _run_metadata_for_request(request: Request, project_name: str, run_name: str) -> RunMetadataStorage:
    """Build run metadata storage for the request's tenant.

    A libSQL tenant's metadata is persisted to its libSQL ``run_meta`` table (so
    the dashboard's :class:`LibsqlCatalog` reads it back); other tenants use the
    filesystem ``*.meta.json`` file. The returned object exposes the same write API
    either way; callers must ``close()`` it (a no-op for filesystem storage).
    """
    tenant_id = tenant_id_from_headers(request.headers)
    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        from aspara.storage.metadata.libsql import LibsqlRunMetadataStorage

        return LibsqlRunMetadataStorage(
            spec.base_dir or "",
            project_name,
            run_name,
            database=spec.database,
            auth_token=spec.auth_token,
        )
    data_dir = resolve_data_dir(tenant_id)
    return RunMetadataStorage(
        base_dir=str(data_dir),
        project_name=project_name,
        run_name=run_name,
    )


def _merge_tags(existing: list[str] | None, new_tags: list[str]) -> list[str]:
    """Merge tag lists, keeping only strings and de-duplicating while preserving order."""
    existing_tags = [t for t in (existing or []) if isinstance(t, str)]
    added_tags = [t for t in new_tags if isinstance(t, str)]
    seen: set[str] = set()
    merged: list[str] = []
    for tag in existing_tags + added_tags:
        if tag not in seen:
            seen.add(tag)
            merged.append(tag)
    return merged


def _update_project_tags_for_request(request: Request, project_name: str, new_tags: list[str] | None) -> None:
    """Append project-level tags for the request's tenant (libSQL or filesystem)."""
    if not new_tags:
        return
    tenant_id = tenant_id_from_headers(request.headers)
    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        from aspara.storage.metadata.libsql import LibsqlProjectMetadataStorage

        storage = LibsqlProjectMetadataStorage(
            spec.base_dir or "",
            project_name,
            database=spec.database,
            auth_token=spec.auth_token,
        )
        try:
            merged = _merge_tags(storage.get_metadata().get("tags"), new_tags)
            storage.update_metadata({"tags": merged})
        except Exception as e:  # pragma: no cover - metadata writes must not break tracking
            logger.warning(f"Failed to update project metadata tags for '{project_name}': {e}")
        finally:
            storage.close()
        return
    update_project_metadata_tags(
        base_dir=resolve_data_dir(tenant_id),
        project_name=project_name,
        new_tags=new_tags,
    )


def _artifact_base_dir_for_request(request: Request) -> str | None:
    """Return the local filesystem base dir for a tenant's artifact *bytes*.

    Remote libSQL tenants do not store artifact bytes locally (object storage
    comes later). ``None`` means the upload must be rejected — never fall back
    to the shared default data directory.
    """
    tenant_id = tenant_id_from_headers(request.headers)
    root = resolve_artifact_base_dir(tenant_id)
    return str(root) if root is not None else None


def verify_csrf_header(x_requested_with: str | None = Header(None)) -> None:
    """Verify X-Requested-With header for CSRF protection.

    This header cannot be set by cross-origin requests without CORS preflight,
    providing protection against CSRF attacks.

    Args:
        x_requested_with: The X-Requested-With header value

    Raises:
        HTTPException: 403 if header is missing or invalid
    """
    if x_requested_with != "XMLHttpRequest":
        raise HTTPException(
            status_code=403,
            detail="Missing or invalid X-Requested-With header",
        )


@router.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint

    Endpoint for checking system status

    Returns:
        HealthResponse: Always returns {"status": "ok"}
    """
    return HealthResponse()


@router.post(
    "/api/v1/projects/{project_name}/runs",
    response_model=RunCreateResponse,
    tags=["Runs"],
    dependencies=[Depends(verify_csrf_header)],
)
async def create_run(project_name: str, request: RunCreateRequest, http_request: Request) -> RunCreateResponse:
    """Create a new run and initialize metadata.

    This endpoint is used by RemoteRun to create run-level metadata and
    update project-level metadata tags. It mirrors LocalRun behaviour
    for metadata semantics. Metadata is routed to the request's tenant
    (a libSQL database for a libSQL tenant, else the filesystem data dir).

    Args:
        project_name: Target project name
        request: Run creation request containing name, tags, notes, config, and project_tags
        http_request: Incoming HTTP request (carries the tenant header)

    Returns:
        RunCreateResponse: Response containing project, name, and run_id

    Raises:
        HTTPException: If a run with the same name already exists (409 Conflict)
    """
    # Validate input names to prevent path traversal
    try:
        validators.validate_project_name(project_name)
        validators.validate_run_name(request.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    if is_read_only():
        return RunCreateResponse(
            project=project_name,
            name=request.name,
            run_id="readonly00000000",
        )

    storage = _run_metadata_for_request(http_request, project_name, request.name)
    try:
        if storage.exists():
            if not request.resume:
                raise HTTPException(status_code=409, detail="Run already exists")
            # Resume path: reuse existing run_id and reset finish state.
            run_id = storage.get_metadata().get("run_id") or uuid.uuid4().hex[:16]
            storage.reset_finish()
            if request.config:
                storage.update_config(request.config)
        else:
            # Initialize run-level metadata. The server always generates run_id.
            now = int(datetime.now(timezone.utc).timestamp() * 1000)
            run_id = uuid.uuid4().hex[:16]
            storage.set_init(
                run_id=run_id,
                tags=request.tags,
                notes=request.notes,
                timestamp=now,
            )
            if request.config:
                storage.update_config(request.config)
    finally:
        storage.close()

    # Update project-level metadata with project_tags, if provided.
    if request.project_tags:
        _update_project_tags_for_request(http_request, project_name, request.project_tags)

    return RunCreateResponse(
        project=project_name,
        name=request.name,
        run_id=run_id,
    )


@router.post(
    "/api/v1/projects/{project_name}/runs/{run_name}/metrics",
    response_model=MetricsResponse,
    tags=["Metrics"],
    dependencies=[Depends(verify_csrf_header)],
)
async def save_metrics(
    project_name: str,
    run_name: str,
    data: MetricRecord,
    request: Request,
) -> MetricsResponse:
    """Endpoint for saving metrics

    Receives and saves run metrics data

    Args:
        project_name: Target project name
        run_name: Target run name
        data: Metrics data to save

    Returns:
        MetricsResponse: Response

    Raises:
        HTTPException: If validation fails
    """
    # Validate input names to prevent path traversal
    try:
        validators.validate_project_name(project_name)
        validators.validate_run_name(run_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    if is_read_only():
        return MetricsResponse()

    try:
        # Create storage for this project/run, routed to the request's tenant
        # (libSQL database for a libSQL tenant, else the filesystem data dir).
        storage = _metrics_storage_for_request(request, project_name, run_name)
        try:
            # Use mode='json' to convert datetime to ISO format string.
            # libSQL connect/DDL/INSERT is sync and can RTT; don't block the loop.
            await asyncio.to_thread(storage.save, data.model_dump(mode="json"))
            return MetricsResponse()
        finally:
            storage.close()
    except ValueError as e:
        # Validation errors are safe to return
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # Log the error but don't expose internal details
        logger.error(f"Error saving metrics: {e}")
        raise HTTPException(status_code=400, detail="Failed to save metrics") from e


@router.post(
    "/api/v1/projects/{project_name}/runs/{run_name}/artifacts",
    response_model=ArtifactUploadResponse,
    tags=["Artifacts"],
    dependencies=[Depends(verify_csrf_header)],
)
async def upload_artifact(
    project_name: str,
    run_name: str,
    file: UploadFile,
    http_request: Request,
    name: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
) -> ArtifactUploadResponse:
    """Upload an artifact file for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        file: File to upload
        http_request: Incoming HTTP request (carries the tenant header)
        name: Optional custom name for the artifact. If None, uses the filename.
        description: Optional description of the artifact
        category: Optional category ('code', 'model', 'config', 'data', 'other')

    Returns:
        ArtifactUploadResponse: Response with artifact details

    Raises:
        HTTPException: If validation fails or file operation fails
    """
    try:
        # Validate input names to prevent path traversal
        try:
            validators.validate_project_name(project_name)
            validators.validate_run_name(run_name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        if is_read_only():
            return ArtifactUploadResponse(
                artifact_name=name or file.filename or "readonly",
                file_size=0,
            )

        # Validate category if provided
        if category and category not in ("code", "model", "config", "data", "other"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category}. Must be one of: code, model, config, data, other",
            )

        # Determine artifact name
        artifact_name = name or file.filename
        if not artifact_name:
            raise HTTPException(status_code=400, detail="Artifact name cannot be empty")

        # Validate artifact name to prevent path traversal
        try:
            validators.validate_artifact_name(artifact_name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        # Remote libSQL tenants have no local artifact root. Do not fall back
        # to the shared data_dir (that would mix tenants); object storage later.
        artifact_root = _artifact_base_dir_for_request(http_request)
        if artifact_root is None:
            raise HTTPException(
                status_code=501,
                detail="Artifact uploads are not supported for remote tenants",
            )

        # Save uploaded file with streaming size enforcement via the artifact
        # store. UploadFile.size may be None under chunked transfer encoding,
        # so we stream fixed-size chunks and let the store enforce the limit
        # (ASPARA_MAX_FILE_SIZE / ResourceLimits.max_file_size) and clean up
        # partial files. Local libSQL tenants pin bytes under ``base_dir``;
        # metadata still lives in the tenant's libSQL database.
        store = FilesystemArtifactStore(artifact_root)
        max_file_size = get_resource_limits().max_file_size

        def _iter_chunks() -> Iterator[bytes]:
            chunk_size = 1 << 20  # 1 MiB
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        try:
            stored = store.put_stream(
                project_name,
                run_name,
                artifact_name,
                _iter_chunks(),
                max_size=max_file_size,
            )
        except ArtifactTooLargeError:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: exceeds limit of {max_file_size} bytes",
            ) from None
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        except Exception as e:
            logger.error(f"Error writing artifact {artifact_name}: {e}")
            raise HTTPException(status_code=500, detail="Failed to write artifact") from e

        logger.info(f"Uploaded artifact: {artifact_name} to {project_name}/{run_name}")

        # Get file size
        file_size = stored.size

        # Prepare artifact metadata
        artifact_data = {
            "name": artifact_name,
            "original_path": file.filename or artifact_name,
            "stored_path": os.path.join("artifacts", artifact_name),
            "file_size": file_size,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }

        if description:
            artifact_data["description"] = description

        if category:
            artifact_data["category"] = category

        # Save artifact metadata to the tenant's metadata store (libSQL or file).
        metadata_storage = _run_metadata_for_request(http_request, project_name, run_name)
        try:
            metadata_storage.add_artifact(artifact_data)
        finally:
            metadata_storage.close()

        return ArtifactUploadResponse(
            artifact_name=artifact_name,
            file_size=file_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log the error but don't expose internal details
        logger.error(f"Error uploading artifact: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload artifact") from e


@router.post(
    "/api/v1/projects/{project_name}/runs/{run_name}/config",
    response_model=StatusResponse,
    tags=["Runs"],
    dependencies=[Depends(verify_csrf_header)],
)
async def update_config(
    project_name: str,
    run_name: str,
    request: ConfigUpdateRequest,
    http_request: Request,
) -> StatusResponse:
    """Update configuration for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Config update request containing config dict
        http_request: Incoming HTTP request (carries the tenant header)

    Returns:
        StatusResponse: Response with status

    Raises:
        HTTPException: If validation fails or run doesn't exist
    """
    # Validate input names to prevent path traversal
    try:
        validators.validate_project_name(project_name)
        validators.validate_run_name(run_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    if is_read_only():
        return StatusResponse()

    storage = _run_metadata_for_request(http_request, project_name, run_name)
    try:
        if not storage.exists():
            raise HTTPException(status_code=404, detail="Run not found")
        storage.update_config(request.config)
        return StatusResponse()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update config") from e
    finally:
        storage.close()


@router.post(
    "/api/v1/projects/{project_name}/runs/{run_name}/summary",
    response_model=StatusResponse,
    tags=["Runs"],
    dependencies=[Depends(verify_csrf_header)],
)
async def update_summary(
    project_name: str,
    run_name: str,
    request: SummaryUpdateRequest,
    http_request: Request,
) -> StatusResponse:
    """Update summary for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Summary update request containing summary dict
        http_request: Incoming HTTP request (carries the tenant header)

    Returns:
        StatusResponse: Response with status

    Raises:
        HTTPException: If validation fails or run doesn't exist
    """
    # Validate input names to prevent path traversal
    try:
        validators.validate_project_name(project_name)
        validators.validate_run_name(run_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    if is_read_only():
        return StatusResponse()

    storage = _run_metadata_for_request(http_request, project_name, run_name)
    try:
        if not storage.exists():
            raise HTTPException(status_code=404, detail="Run not found")
        storage.update_summary(request.summary)
        return StatusResponse()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to update summary") from e
    finally:
        storage.close()


@router.post(
    "/api/v1/projects/{project_name}/runs/{run_name}/finish",
    response_model=StatusResponse,
    tags=["Runs"],
    dependencies=[Depends(verify_csrf_header)],
)
async def finish_run(
    project_name: str,
    run_name: str,
    request: FinishRequest,
    http_request: Request,
) -> StatusResponse:
    """Finish a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Finish request containing exit_code
        http_request: Incoming HTTP request (carries the tenant header)

    Returns:
        StatusResponse: Response with status

    Raises:
        HTTPException: If validation fails or run doesn't exist
    """
    # Validate input names to prevent path traversal
    try:
        validators.validate_project_name(project_name)
        validators.validate_run_name(run_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    if is_read_only():
        return StatusResponse()

    storage = _run_metadata_for_request(http_request, project_name, run_name)
    try:
        if not storage.exists():
            raise HTTPException(status_code=404, detail="Run not found")
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        storage.set_finish(exit_code=request.exit_code, timestamp=now)
        return StatusResponse()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finishing run: {e}")
        raise HTTPException(status_code=500, detail="Failed to finish run") from e
    finally:
        storage.close()


@router.post(
    "/api/v1/projects/{project_name}/runs/{run_name}/tags",
    response_model=StatusResponse,
    tags=["Runs"],
    dependencies=[Depends(verify_csrf_header)],
)
async def update_tags(
    project_name: str,
    run_name: str,
    request: TagsUpdateRequest,
    http_request: Request,
) -> StatusResponse:
    """Update tags for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Tags update request containing the new tag list
        http_request: Incoming HTTP request (carries the tenant header)

    Returns:
        StatusResponse: Response with status

    Raises:
        HTTPException: If validation fails or run doesn't exist
    """
    # Validate input names to prevent path traversal
    try:
        validators.validate_project_name(project_name)
        validators.validate_run_name(run_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    if is_read_only():
        return StatusResponse()

    storage = _run_metadata_for_request(http_request, project_name, run_name)
    try:
        if not storage.exists():
            raise HTTPException(status_code=404, detail="Run not found")
        storage.set_tags(request.tags)
        return StatusResponse()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tags: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tags") from e
    finally:
        storage.close()
