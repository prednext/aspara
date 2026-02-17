"""
JsonlMetricsStorage - JSONL file-based metrics storage.

This module provides a simple, portable storage backend using JSONL files.
Timestamps are stored as UNIX milliseconds (UTC) for efficient parsing with Polars.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from aspara.config import get_resource_limits
from aspara.exceptions import RunNotFoundError
from aspara.utils import datasync, secure_open_append

from .base import MetricsStorage


class JsonlMetricsStorage(MetricsStorage):
    """JSONL file-based metrics storage.

    Stores metrics data in JSONL (JSON Lines) format, with one JSON object per line.
    This format is simple, human-readable, and easy to append to.
    """

    def __init__(self, base_dir: str | Path, project_name: str, run_name: str) -> None:
        """Initialize JSONL storage.

        Args:
            base_dir: Base directory for data storage
            project_name: Project name
            run_name: Run name
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True, parents=True)
        self.project_name = project_name
        self.run_name = run_name

    def _get_run_file(self) -> Path:
        """Get the path to this run's JSONL file.

        Returns:
            Path to the JSONL file
        """
        project_dir = self.base_dir / self.project_name
        project_dir.mkdir(exist_ok=True, parents=True)
        return project_dir / f"{self.run_name}.jsonl"

    def save(self, metrics_data: dict[str, Any]) -> str:
        """Save metrics data to JSONL file.

        Args:
            metrics_data: Metrics data to save

        Returns:
            str: Empty string

        Raises:
            ValueError: If file size exceeds limit
        """
        run_file = self._get_run_file()
        limits = get_resource_limits()

        # Serialize data first to know the size before opening the file
        new_data = json.dumps(metrics_data) + "\n"
        new_data_bytes = new_data.encode("utf-8")

        # Open file securely with proper permissions (0o600)
        with secure_open_append(run_file) as f:
            # Get current file size after opening (avoids race condition)
            f.seek(0, 2)  # Seek to end
            current_size = f.tell()

            # Check if adding new data would exceed limit
            if current_size + len(new_data_bytes) > limits.max_file_size:
                raise ValueError(f"File size limit would be exceeded: {current_size} + {len(new_data_bytes)} bytes (max: {limits.max_file_size} bytes)")

            f.write(new_data)
            f.flush()
            datasync(f.fileno())

        return ""

    def load(
        self,
        metric_names: list[str] | None = None,
    ) -> pl.DataFrame:
        """Load metrics data from JSONL file in wide format.

        Uses Polars lazy API for optimized query execution.

        Args:
            metric_names: Optional list of metric names to filter by

        Returns:
            Polars DataFrame in wide format with columns:
            - timestamp: Datetime
            - step: Int64
            - _<metric_name>: Float64 for each metric (underscore-prefixed)

        Raises:
            RunNotFoundError: If the run file does not exist
        """
        run_file = self._get_run_file()

        if not run_file.exists():
            raise RunNotFoundError(f"Run '{self.run_name}' not found in project '{self.project_name}'")

        # Use lazy scan for optimized query planning
        lf = pl.scan_ndjson(run_file)

        # Get schema to check columns (need to collect for schema inspection)
        schema = lf.collect_schema()

        if len(schema) == 0:
            return pl.DataFrame(
                schema={
                    "timestamp": pl.Datetime,
                    "step": pl.Int64,
                }
            )

        # Build transformation chain using lazy API
        if "metrics" in schema:
            # Unnest the metrics struct to get individual metric columns
            lf = lf.unnest("metrics")

            # Re-fetch schema after unnest
            schema = lf.collect_schema()

            # Rename metric columns to add underscore prefix
            # (excluding timestamp and step)
            metric_cols = [col for col in schema.names() if col not in ["timestamp", "step", "project_name", "run_name"]]
            rename_map = {col: f"_{col}" for col in metric_cols}
            lf = lf.rename(rename_map)

            # Filter by metric names if specified
            if metric_names is not None:
                keep_cols = ["timestamp", "step"] + [f"_{name}" for name in metric_names if f"_{name}" in lf.collect_schema().names()]
                lf = lf.select(keep_cols)

        # Timestamp conversion - UNIX ms to Datetime
        if "timestamp" in lf.collect_schema():
            lf = lf.with_columns(pl.col("timestamp").cast(pl.Datetime("ms")))

        # Sort by timestamp and step, then collect
        return lf.sort(["timestamp", "step"]).collect()

    def close(self) -> None:
        """Close storage backend.

        This backend doesn't hold long-lived connections, so this is a no-op.
        """
        pass
