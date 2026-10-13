"""
Aspara core data models for metric records.

This module contains the central data model used across all components
for representing individual metric records.
"""

import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class MetricRecord(BaseModel):
    """Unified metric record for all Aspara components

    This class represents a single metric record with timestamp, step, and metrics.
    Used by both tracker API and catalog components.
    """

    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now, description="Recording timestamp")
    step: int | None = Field(default=None, description="Step number (optional)")
    metrics: dict[str, Any] = Field(..., description="Dictionary of metric names and their values")
    run: str | None = Field(default=None, description="Run name (optional, useful for multi-run watch)")
    project: str | None = Field(default=None, description="Project name (optional, useful for multi-run watch)")

    @model_validator(mode="wrap")
    @classmethod
    def _accept_unix_ms(cls, value: Any, handler: Any) -> "MetricRecord":
        """Keep a client-supplied UNIX millisecond timestamp exact."""
        raw_ms: int | None = None
        if isinstance(value, dict):
            ts = value.get("timestamp")
            if isinstance(ts, (int, float)) and not isinstance(ts, bool):
                raw_ms = int(ts)
                value = dict(value)
                value["timestamp"] = datetime.datetime.fromtimestamp(raw_ms / 1000, tz=datetime.timezone.utc)
        model = handler(value)
        if raw_ms is not None:
            object.__setattr__(model, "_client_timestamp_ms", raw_ms)
        return model

    def timestamp_ms(self) -> int:
        """UNIX milliseconds to store. Client-supplied ints are not re-clocked."""
        raw = getattr(self, "_client_timestamp_ms", None)
        if isinstance(raw, int):
            return raw
        return int(round(self.timestamp.timestamp() * 1000))

    def __str__(self) -> str:
        """String representation of the metric record."""
        return f"MetricRecord(timestamp={self.timestamp}, step={self.step}, metrics={list(self.metrics.keys())})"


class StatusRecord(BaseModel):
    """Run status update record.

    Represents a change in run status (e.g., from WIP to COMPLETED).
    """

    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now, description="Update timestamp")
    run: str = Field(..., description="Run name")
    project: str = Field(..., description="Project name")
    status: str = Field(..., description="New status value")
    is_finished: bool = Field(..., description="Whether run is finished")
    exit_code: int | None = Field(default=None, description="Exit code if finished")

    def __str__(self) -> str:
        return f"StatusRecord(run={self.run}, status={self.status})"
