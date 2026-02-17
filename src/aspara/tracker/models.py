"""
Aspara Tracker data model definitions
"""

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str = "ok"


class MetricsResponse(BaseModel):
    """Metrics save response model"""

    status: str = "ok"


class MetricsListResponse(BaseModel):
    """Metrics list response model"""

    metrics: list[dict[str, Any]]


class ProjectsResponse(BaseModel):
    """Projects list response model"""

    projects: list[str]


class RunsResponse(BaseModel):
    """Runs list response model"""

    runs: list[str]


class RunCreateRequest(BaseModel):
    """Request model for creating a new run via tracker API."""

    name: str
    config: dict[str, Any] = {}
    tags: list[str] = []
    notes: str = ""
    project_tags: list[str] | None = None


class RunCreateResponse(BaseModel):
    """Response model for run creation endpoint."""

    status: str = "ok"
    project: str
    name: str
    run_id: str


class ArtifactUploadResponse(BaseModel):
    """Response model for artifact upload endpoint."""

    status: str = "ok"
    artifact_name: str
    file_size: int


class ConfigUpdateRequest(BaseModel):
    """Request model for updating run config."""

    config: dict[str, Any] = {}


class SummaryUpdateRequest(BaseModel):
    """Request model for updating run summary."""

    summary: dict[str, Any] = {}


class FinishRequest(BaseModel):
    """Request model for finishing a run."""

    exit_code: int = 0


class StatusResponse(BaseModel):
    """Generic status response model."""

    status: str = "ok"
