"""
Models for metrics data.

This module defines the data models for the dashboard API.
Note: experiment concept has been removed - data structure is now project/run.
"""

from datetime import datetime

from pydantic import BaseModel

from aspara.catalog.project_catalog import ProjectInfo
from aspara.catalog.run_catalog import RunInfo

__all__ = [
    "Metadata",
    "MetadataUpdateRequest",
    "MetricSeries",
    "ProjectInfo",
    "RunInfo",
]


class Metadata(BaseModel):
    """Metadata for projects and runs."""

    notes: str = ""
    tags: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MetadataUpdateRequest(BaseModel):
    """Request model for updating metadata."""

    notes: str | None = None
    tags: list[str] | None = None


class MetricSeries(BaseModel):
    """A single metric time series with steps, values, and timestamps.

    Used in the metrics API response to represent one metric's data.
    Arrays are delta-compressed where applicable.
    """

    steps: list[int | float]
    values: list[int | float]
    timestamps: list[int | float]
