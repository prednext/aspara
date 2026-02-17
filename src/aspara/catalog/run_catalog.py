"""
RunCatalog - Catalog for discovering and managing runs within a project.

This module provides functionality for listing, getting, and deleting runs
in a project directory.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil
from collections.abc import AsyncGenerator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import BaseModel, Field

from aspara.exceptions import ProjectNotFoundError, RunNotFoundError
from aspara.models import MetricRecord, RunStatus, StatusRecord
from aspara.storage import RunMetadataStorage
from aspara.utils.timestamp import parse_to_datetime
from aspara.utils.validators import validate_name, validate_safe_path

logger = logging.getLogger(__name__)

# Threshold in seconds to consider a run as potentially failed (1 hour)
STALE_RUN_THRESHOLD_SECONDS = 3600


class RunInfo(BaseModel):
    """Run information."""

    name: str
    run_id: str | None = None
    start_time: datetime | None = None
    last_update: datetime | None = None
    param_count: int
    artifact_count: int = 0
    tags: list[str] = []
    is_corrupted: bool = False
    error_message: str | None = None
    is_finished: bool = False
    exit_code: int | None = None
    status: RunStatus = Field(default=RunStatus.WIP)


def _detect_backend(data_dir: Path, project: str, run_name: str) -> str:
    """Detect which storage backend a run is using.

    Args:
        data_dir: Base data directory
        project: Project name
        run_name: Run name

    Returns:
        "polars" if the run uses Polars backend (WAL + Parquet), "jsonl" otherwise
    """
    project_dir = data_dir / project

    # Check for Polars backend indicators
    wal_file = project_dir / f"{run_name}.wal.jsonl"
    archive_dir = project_dir / f"{run_name}_archive"

    # If WAL file or archive directory exists, it's a Polars backend
    if wal_file.exists() or archive_dir.exists():
        return "polars"

    # Otherwise, it's JSONL backend
    return "jsonl"


def _open_metrics_storage(
    base_dir: Path | str,
    project: str,
    run_name: str,
):
    """Open metrics storage for an existing run.

    Detects the backend type from existing files and returns
    the appropriate storage instance.

    Args:
        base_dir: Base data directory
        project: Project name
        run_name: Run name

    Returns:
        JsonlMetricsStorage or PolarsMetricsStorage instance
    """
    from aspara.storage import JsonlMetricsStorage, PolarsMetricsStorage

    backend = _detect_backend(Path(base_dir), project, run_name)

    if backend == "polars":
        return PolarsMetricsStorage(
            base_dir=str(base_dir),
            project_name=project,
            run_name=run_name,
        )
    else:
        return JsonlMetricsStorage(
            base_dir=str(base_dir),
            project_name=project,
            run_name=run_name,
        )


def _read_metadata_file(metadata_file: Path) -> dict:
    """Read .meta.json file and return parsed data.

    Args:
        metadata_file: Path to the .meta.json file

    Returns:
        Dictionary with metadata, or empty dict if file doesn't exist or is invalid
    """
    if not metadata_file.exists():
        return {}

    try:
        with open(metadata_file) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error reading metadata file {metadata_file}: {e}")
        return {}


def _infer_stale_status(
    status: RunStatus,
    start_time: datetime | None,
    is_finished: bool,
) -> RunStatus:
    """Infer MAYBE_FAILED status for old runs that were never finished.

    Args:
        status: Current run status
        start_time: When the run started
        is_finished: Whether the run has finished

    Returns:
        MAYBE_FAILED if run is stale, otherwise the original status
    """
    if status != RunStatus.WIP or not start_time or is_finished:
        return status

    current_time = datetime.now(timezone.utc)
    age_seconds = (current_time - start_time).total_seconds()
    if age_seconds > STALE_RUN_THRESHOLD_SECONDS:
        return RunStatus.MAYBE_FAILED

    return status


def _extract_timestamp_range(
    df: pl.DataFrame,
) -> tuple[datetime | None, datetime | None]:
    """Extract start_time and last_update from DataFrame.

    Args:
        df: DataFrame with timestamp column

    Returns:
        Tuple of (start_time, last_update)
    """
    if len(df) == 0 or "timestamp" not in df.columns:
        return (None, None)

    timestamps = df.select("timestamp").to_series()
    if len(timestamps) == 0:
        return (None, None)

    ts_min = timestamps.min()
    ts_max = timestamps.max()

    start_time = ts_min if isinstance(ts_min, datetime) else None
    last_update = ts_max if isinstance(ts_max, datetime) else None

    return (start_time, last_update)


def _check_corruption(
    df: pl.DataFrame,
    metadata_file_exists: bool,
) -> tuple[bool, str | None]:
    """Check if metrics data is corrupted.

    Args:
        df: DataFrame with metrics
        metadata_file_exists: Whether metadata file exists

    Returns:
        Tuple of (is_corrupted, error_message)
    """
    if len(df) == 0 and not metadata_file_exists:
        return (True, "Empty file! No data found!")
    if len(df) > 0 and "timestamp" not in df.columns:
        return (True, "No timestamps found! Corrupted Run!")
    return (False, None)


def _map_error_to_corruption(
    error: Exception,
    metadata_file_exists: bool,
) -> tuple[bool, str | None]:
    """Map storage read errors to corruption status.

    Args:
        error: The exception that occurred
        metadata_file_exists: Whether metadata file exists

    Returns:
        Tuple of (is_corrupted, error_message)
    """
    error_str = str(error).lower()

    if "empty" in error_str or "empty string" in error_str:
        return (True, "Empty file! No data found!")
    if "expectedobjectkey" in error_str.replace(" ", "") or "invalid json" in error_str:
        return (True, f"Invalid file format! Error: {error!s}")
    if "timestamp" in error_str:
        return (True, f"No timestamps found! Error: {error!s}")
    if "step" in error_str and not metadata_file_exists:
        return (True, f"Failed to read metrics: {error!s}")
    if not metadata_file_exists:
        return (True, f"Failed to read metrics: {error!s}")

    return (False, None)


class RunCatalog:
    """Catalog for discovering and managing runs within a project.

    This class provides methods to list, get, delete, and watch runs.
    It handles both JSONL and DuckDB storage formats.
    """

    def __init__(self, data_dir: str | Path) -> None:
        """Initialize the run catalog.

        Args:
            data_dir: Base directory for data storage
        """
        self.data_dir = Path(data_dir)

    def _parse_file_path(self, file_path: Path) -> tuple[str, str, str] | None:
        """Parse file path to extract project, run name, and file type.

        Args:
            file_path: Absolute path to a file (e.g., data/project/run.jsonl)

        Returns:
            (project, run_name, file_type) where file_type is 'metrics', 'wal', or 'meta'
            None if path doesn't match expected pattern
        """
        try:
            relative = file_path.relative_to(self.data_dir)
        except ValueError:
            return None

        parts = relative.parts
        if len(parts) != 2:
            return None

        project = parts[0]
        filename = parts[1]

        if filename.endswith(".wal.jsonl"):
            return (project, filename[:-10], "wal")
        elif filename.endswith(".meta.json"):
            return (project, filename[:-10], "meta")
        elif filename.endswith(".jsonl"):
            return (project, filename[:-6], "metrics")

        return None

    def _read_run_info(self, project: str, run_name: str, run_file: Path) -> RunInfo:
        """Read run information from JSONL metrics file and metadata file.

        Supports both JSONL and Polars backends.
        Optimization: Avoids loading full DataFrame when metadata provides sufficient info.

        Args:
            project: Project name
            run_name: Run name
            run_file: Path to the JSONL metrics file

        Returns:
            RunInfo object with metadata from both files
        """
        metadata_file = run_file.parent / f"{run_name}.meta.json"

        # Read metadata
        metadata = _read_metadata_file(metadata_file)
        run_id = metadata.get("run_id")
        tags = metadata.get("tags", [])
        is_finished = metadata.get("is_finished", False)
        exit_code = metadata.get("exit_code")

        # Read params count
        params = metadata.get("params", {})
        params_count = len(params) if isinstance(params, dict) else 0

        # Parse status
        status_value = metadata.get("status", RunStatus.WIP.value)
        try:
            status = RunStatus(status_value)
        except ValueError:
            status = RunStatus.from_is_finished_and_exit_code(is_finished, exit_code)

        # Parse start_time from metadata
        start_time = None
        start_time_value = metadata.get("start_time")
        if start_time_value is not None:
            with contextlib.suppress(ValueError):
                start_time = parse_to_datetime(start_time_value)

        # Infer stale status
        status = _infer_stale_status(status, start_time, is_finished)

        # Lightweight corruption check: file exists and is not empty
        is_corrupted = False
        error_message = None
        last_update = None

        # Use file modification time as last_update
        if run_file.exists():
            last_update = datetime.fromtimestamp(run_file.stat().st_mtime)

        if not run_file.exists() and not metadata_file.exists():
            is_corrupted = True
            error_message = "Run file not found"
        elif run_file.exists() and run_file.stat().st_size == 0 and not metadata_file.exists():
            is_corrupted = True
            error_message = "Empty file! No data found!"

        return RunInfo(
            name=run_name,
            run_id=run_id,
            start_time=start_time,
            last_update=last_update,
            param_count=params_count,
            artifact_count=0,
            tags=tags,
            is_corrupted=is_corrupted,
            error_message=error_message,
            is_finished=is_finished,
            exit_code=exit_code,
            status=status,
        )

    def get_runs(self, project: str) -> list[RunInfo]:
        """List all runs in a project.

        Args:
            project: Project name

        Returns:
            List of RunInfo objects sorted by name

        Raises:
            ValueError: If project name is invalid
            ProjectNotFoundError: If project does not exist
        """
        validate_name(project, "project name")

        project_dir = self.data_dir / project
        validate_safe_path(project_dir, self.data_dir)

        if not project_dir.exists():
            raise ProjectNotFoundError(f"Project '{project}' not found")

        runs = []
        seen_run_names: set[str] = set()

        # Process .jsonl files (including .wal.jsonl for Polars backend)
        for run_file in list(project_dir.glob("*.jsonl")):
            # Determine run name from file
            if run_file.name.endswith(".wal.jsonl"):
                # Skip WAL files - they're handled by metadata
                continue
            else:
                run_name = run_file.stem

            # Skip if we've already processed this run
            if run_name in seen_run_names:
                continue
            seen_run_names.add(run_name)

            # Handle plain JSONL files
            run = self._read_run_info(project, run_name, run_file)
            runs.append(run)

        return sorted(runs, key=lambda r: r.name)

    def get(self, project: str, run: str) -> RunInfo:
        """Get a specific run.

        Args:
            project: Project name
            run: Run name

        Returns:
            RunInfo object

        Raises:
            ValueError: If project or run name is invalid
            ProjectNotFoundError: If project does not exist
            RunNotFoundError: If run does not exist
        """
        validate_name(project, "project name")
        validate_name(run, "run name")

        project_dir = self.data_dir / project
        validate_safe_path(project_dir, self.data_dir)

        if not project_dir.exists():
            raise ProjectNotFoundError(f"Project '{project}' not found")

        # Check for JSONL file
        jsonl_file = project_dir / f"{run}.jsonl"

        if jsonl_file.exists():
            return self._read_run_info(project, run, jsonl_file)
        else:
            raise RunNotFoundError(f"Run '{run}' not found in project '{project}'")

    def delete(self, project: str, run: str) -> None:
        """Delete a run and its artifacts.

        Args:
            project: Project name
            run: Run name to delete

        Raises:
            ValueError: If project or run name is empty or invalid
            ProjectNotFoundError: If project does not exist
            RunNotFoundError: If run does not exist
            PermissionError: If deletion is not permitted
        """
        if not project:
            raise ValueError("Project name cannot be empty")
        if not run:
            raise ValueError("Run name cannot be empty")

        validate_name(project, "project name")
        validate_name(run, "run name")

        project_dir = self.data_dir / project
        validate_safe_path(project_dir, self.data_dir)

        if not project_dir.exists():
            raise ProjectNotFoundError(f"Project '{project}' does not exist")

        # Check for any run files
        wal_file = project_dir / f"{run}.wal.jsonl"
        jsonl_file = project_dir / f"{run}.jsonl"

        if not wal_file.exists() and not jsonl_file.exists():
            raise RunNotFoundError(f"Run '{run}' does not exist in project '{project}'")

        try:
            # Delete all run-related files
            metadata_file = project_dir / f"{run}.meta.json"
            for file_path in [wal_file, jsonl_file, metadata_file]:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Deleted file: {file_path}")

            # Delete artifacts directory if it exists
            artifacts_dir = project_dir / run / "artifacts"
            run_dir = project_dir / run

            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir)
                logger.debug(f"Deleted artifacts for {project}/{run}")

            # Delete run directory if it exists and is empty
            if run_dir.exists():
                try:
                    run_dir.rmdir()
                    logger.debug(f"Deleted run directory for {project}/{run}")
                except OSError:
                    pass

            logger.info(f"Successfully deleted run: {project}/{run}")
        except (PermissionError, OSError) as e:
            logger.error(f"Error deleting run {project}/{run}: {type(e).__name__}")
            raise

    def exists(self, project: str, run: str) -> bool:
        """Check if a run exists.

        Args:
            project: Project name
            run: Run name

        Returns:
            True if run exists, False otherwise
        """
        try:
            validate_name(project, "project name")
            validate_name(run, "run name")

            project_dir = self.data_dir / project
            validate_safe_path(project_dir, self.data_dir)

            wal_file = project_dir / f"{run}.wal.jsonl"
            jsonl_file = project_dir / f"{run}.jsonl"

            return wal_file.exists() or jsonl_file.exists()
        except ValueError:
            return False

    async def subscribe(
        self,
        targets: Mapping[str, list[str] | None],
        since: datetime,
    ) -> AsyncGenerator[MetricRecord | StatusRecord, None]:
        """Subscribe to file changes for specified targets using DataDirWatcher.

        This method uses a singleton DataDirWatcher instance to minimize inotify
        file descriptor usage. Multiple SSE connections share the same watcher.

        Args:
            targets: Dictionary mapping project names to list of run names.
                     If run list is None, all runs in the project are watched.
            since: Filter to only yield records with timestamp >= since

        Yields:
            MetricRecord or StatusRecord as files are updated
        """
        from aspara.catalog.watcher import DataDirWatcher

        watcher = await DataDirWatcher.get_instance(self.data_dir)
        async for record in watcher.subscribe(targets, since):
            yield record

    def get_artifacts(self, project: str, run: str) -> list[dict]:
        """Get artifacts for a run from metadata file.

        Args:
            project: Project name
            run: Run name

        Returns:
            List of artifact dictionaries
        """
        validate_name(project, "project name")
        validate_name(run, "run name")

        # Read from metadata file
        metadata_file = self.data_dir / project / f"{run}.meta.json"
        validate_safe_path(metadata_file, self.data_dir)

        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                    return metadata.get("artifacts", [])
            except Exception as e:
                logger.warning(f"Error reading artifacts from metadata file for {run}: {e}")

        return []

    def get_metadata(self, project: str, run: str) -> dict:
        """Get run metadata from .meta.json file.

        Args:
            project: Project name
            run: Run name

        Returns:
            Dictionary containing run metadata
        """
        storage = RunMetadataStorage(self.data_dir, project, run)
        return storage.get_metadata()

    def update_metadata(self, project: str, run: str, metadata: dict) -> dict:
        """Update run metadata in .meta.json file.

        Args:
            project: Project name
            run: Run name
            metadata: Dictionary with fields to update (notes, tags)

        Returns:
            Updated complete metadata dictionary
        """
        storage = RunMetadataStorage(self.data_dir, project, run)
        return storage.update_metadata(metadata)

    def delete_metadata(self, project: str, run: str) -> bool:
        """Delete run metadata file.

        Args:
            project: Project name
            run: Run name

        Returns:
            True if file was deleted, False if it didn't exist
        """
        storage = RunMetadataStorage(self.data_dir, project, run)
        return storage.delete_metadata()

    def _guess_artifact_category(self, filename: str) -> str:
        """Guess artifact category from file extension.

        Args:
            filename: Name of the artifact file

        Returns:
            Category string
        """
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        if ext in ["py", "js", "ts", "jsx", "tsx", "cpp", "c", "h", "java", "go", "rs", "rb", "php"]:
            return "code"
        if ext in ["yaml", "yml", "json", "toml", "ini", "cfg", "conf", "env"]:
            return "config"
        if ext in ["pt", "pth", "pkl", "pickle", "h5", "hdf5", "onnx", "pb", "tflite", "joblib"]:
            return "model"
        if ext in ["csv", "tsv", "parquet", "feather", "xlsx", "xls", "hdf", "npy", "npz"]:
            return "data"

        return "other"

    def load_metrics(
        self,
        project: str,
        run: str,
        start_time: datetime | None = None,
    ) -> pl.DataFrame:
        """Load metrics for a run in wide format (auto-detects storage backend).

        Args:
            project: Project name
            run: Run name
            start_time: Optional start time to filter metrics from

        Returns:
            Polars DataFrame in wide format with columns:
            - timestamp: Datetime
            - step: Int64
            - _<metric_name>: Float64 for each metric (underscore-prefixed)

        Raises:
            ValueError: If project or run name is invalid
            RunNotFoundError: If run does not exist
        """
        validate_name(project, "project name")
        validate_name(run, "run name")

        # Create storage using factory function and load metrics
        storage = _open_metrics_storage(self.data_dir, project, run)

        try:
            df = storage.load()
        except Exception as e:
            logger.warning(f"Failed to load metrics for {project}/{run}: {e}")
            return pl.DataFrame(
                schema={
                    "timestamp": pl.Datetime,
                    "step": pl.Int64,
                }
            )

        # Apply start_time filter if specified
        if start_time is not None and len(df) > 0:
            df = df.filter(pl.col("timestamp") >= start_time)

        return df

    def get_run_config(self, project: str, run: str) -> dict[str, Any]:
        """Get run config from .meta.json file.

        This reads the .meta.json file which contains params, config, status, etc.
        Different from get_metadata which uses ProjectMetadataStorage for notes/tags.

        Args:
            project: Project name
            run: Run name

        Returns:
            Dictionary containing run config (params, config, status, etc.)
        """
        validate_name(project, "project name")
        validate_name(run, "run name")

        metadata_file = self.data_dir / project / f"{run}.meta.json"
        validate_safe_path(metadata_file, self.data_dir)

        return _read_metadata_file(metadata_file)

    async def get_run_config_async(self, project: str, run: str) -> dict[str, Any]:
        """Get run config asynchronously using run_in_executor.

        This reads the .meta.json file which contains params, config, status, etc.

        Args:
            project: Project name
            run: Run name

        Returns:
            Dictionary containing run config (params, config, status, etc.)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_run_config, project, run)

    async def get_metadata_async(self, project: str, run: str) -> dict[str, Any]:
        """Get run metadata asynchronously using run_in_executor.

        Args:
            project: Project name
            run: Run name

        Returns:
            Dictionary containing run metadata (tags, notes, params, etc.)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_metadata, project, run)

    async def get_artifacts_async(self, project: str, run: str) -> list[dict[str, Any]]:
        """Get artifacts for a run asynchronously using run_in_executor.

        Args:
            project: Project name
            run: Run name

        Returns:
            List of artifact dictionaries
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_artifacts, project, run)
