"""Aspara Tracker API router.

RESTful API endpoints using FastAPI APIRouter.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Header, HTTPException, UploadFile

from aspara.config import get_data_dir, get_resource_limits, is_read_only
from aspara.models import MetricRecord
from aspara.storage import RunMetadataStorage, create_metrics_storage
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
async def create_run(project_name: str, request: RunCreateRequest) -> RunCreateResponse:
    """Create a new run and initialize metadata.

    This endpoint is used by RemoteRun to create run-level metadata and
    update project-level metadata tags. It mirrors LocalRun behaviour
    for metadata semantics.

    Args:
        project_name: Target project name
        request: Run creation request containing name, tags, notes, config, and project_tags

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

    data_dir = get_data_dir()
    base_dir = Path(data_dir)

    # Detect existing run by checking metadata file
    metadata_path = base_dir / project_name / f"{request.name}.meta.json"
    if metadata_path.exists():
        if not request.resume:
            raise HTTPException(status_code=409, detail="Run already exists")
        # Resume path: reuse existing run_id and reset finish state.
        try:
            with open(metadata_path) as f:
                existing_meta = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise HTTPException(
                status_code=500,
                detail="Failed to read existing run metadata",
            ) from e
        run_id = existing_meta.get("run_id") or uuid.uuid4().hex[:16]
        storage = RunMetadataStorage(
            base_dir=str(data_dir),
            project_name=project_name,
            run_name=request.name,
        )
        storage.reset_finish()
        if request.config:
            storage.update_config(request.config)
        if request.project_tags:
            update_project_metadata_tags(
                base_dir=data_dir,
                project_name=project_name,
                new_tags=request.project_tags,
            )
        return RunCreateResponse(
            project=project_name,
            name=request.name,
            run_id=run_id,
        )

    # Initialize run-level metadata using RunMetadataStorage
    storage = RunMetadataStorage(
        base_dir=str(data_dir),
        project_name=project_name,
        run_name=request.name,
    )

    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    run_id = uuid.uuid4().hex[:16]  # Server always generates run_id
    storage.set_init(
        run_id=run_id,
        tags=request.tags,
        notes=request.notes,
        timestamp=now,
    )

    if request.config:
        storage.update_config(request.config)

    # Update project-level metadata.json with project_tags, if provided
    if request.project_tags:
        update_project_metadata_tags(
            base_dir=data_dir,
            project_name=project_name,
            new_tags=request.project_tags,
        )

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
        # Create storage instance for this specific project/run
        data_dir = get_data_dir()
        storage = create_metrics_storage(
            backend=None,
            base_dir=str(data_dir),
            project_name=project_name,
            run_name=run_name,
        )
        # Use mode='json' to convert datetime to ISO format string
        storage.save(data.model_dump(mode="json"))
        return MetricsResponse()
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
    name: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
) -> ArtifactUploadResponse:
    """Upload an artifact file for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        file: File to upload
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

        # Set up artifacts directory
        data_dir = get_data_dir()
        base_dir = Path(data_dir)
        artifacts_dir = base_dir / project_name / run_name / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Construct destination path and validate it's within artifacts_dir
        dest_path = artifacts_dir / artifact_name
        try:
            validators.validate_safe_path(dest_path, artifacts_dir)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        # Save uploaded file with streaming size enforcement.
        # UploadFile.size may be None under chunked transfer encoding, so
        # we cannot rely on it alone. Read in fixed-size chunks and track
        # the cumulative bytes written; abort (and clean up the partial
        # file) as soon as the limit is exceeded. The limit is the SSOT
        # value from ResourceLimits.max_file_size (env-configurable via
        # ASPARA_MAX_FILE_SIZE).
        max_file_size = get_resource_limits().max_file_size
        written = 0
        chunk_size = 1 << 20  # 1 MiB
        try:
            with open(dest_path, "wb") as f:
                while True:
                    chunk = file.file.read(chunk_size)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_file_size:
                        f.close()
                        dest_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large: exceeds limit of {max_file_size} bytes",
                        )
                    f.write(chunk)
        except HTTPException:
            raise
        except Exception as e:
            # Clean up partial file on any write error
            dest_path.unlink(missing_ok=True)
            logger.error(f"Error writing artifact {artifact_name}: {e}")
            raise HTTPException(status_code=500, detail="Failed to write artifact") from e

        logger.info(f"Uploaded artifact: {artifact_name} to {project_name}/{run_name}")

        # Get file size
        file_size = written

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

        # Save artifact metadata
        metadata_storage = RunMetadataStorage(
            base_dir=str(data_dir),
            project_name=project_name,
            run_name=run_name,
        )
        metadata_storage.add_artifact(artifact_data)

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
) -> StatusResponse:
    """Update configuration for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Config update request containing config dict

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

    data_dir = get_data_dir()
    base_dir = Path(data_dir)

    # Check if run exists
    metadata_path = base_dir / project_name / f"{run_name}.meta.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        storage = RunMetadataStorage(
            base_dir=str(data_dir),
            project_name=project_name,
            run_name=run_name,
        )
        storage.update_config(request.config)
        return StatusResponse()
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update config") from e


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
) -> StatusResponse:
    """Update summary for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Summary update request containing summary dict

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

    data_dir = get_data_dir()
    base_dir = Path(data_dir)

    # Check if run exists
    metadata_path = base_dir / project_name / f"{run_name}.meta.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        storage = RunMetadataStorage(
            base_dir=str(data_dir),
            project_name=project_name,
            run_name=run_name,
        )
        storage.update_summary(request.summary)
        return StatusResponse()
    except Exception as e:
        logger.error(f"Error updating summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to update summary") from e


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
) -> StatusResponse:
    """Finish a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Finish request containing exit_code

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

    data_dir = get_data_dir()
    base_dir = Path(data_dir)

    # Check if run exists
    metadata_path = base_dir / project_name / f"{run_name}.meta.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        storage = RunMetadataStorage(
            base_dir=str(data_dir),
            project_name=project_name,
            run_name=run_name,
        )
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        storage.set_finish(exit_code=request.exit_code, timestamp=now)
        return StatusResponse()
    except Exception as e:
        logger.error(f"Error finishing run: {e}")
        raise HTTPException(status_code=500, detail="Failed to finish run") from e


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
) -> StatusResponse:
    """Update tags for a run.

    Args:
        project_name: Target project name
        run_name: Target run name
        request: Tags update request containing the new tag list

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

    data_dir = get_data_dir()
    base_dir = Path(data_dir)

    # Check if run exists
    metadata_path = base_dir / project_name / f"{run_name}.meta.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        storage = RunMetadataStorage(
            base_dir=str(data_dir),
            project_name=project_name,
            run_name=run_name,
        )
        storage.set_tags(request.tags)
        return StatusResponse()
    except Exception as e:
        logger.error(f"Error updating tags: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tags") from e
