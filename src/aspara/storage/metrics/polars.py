"""
PolarsMetricsStorage - Polars/PyArrow-based metrics storage with WAL.

This module provides high-performance storage using Polars for data manipulation
and PyArrow for Parquet I/O, with a Write-Ahead Log (WAL) pattern for lock-free concurrent access.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from aspara.exceptions import RunNotFoundError
from aspara.logger import logger
from aspara.utils import datasync, secure_open_append

from .base import MetricsStorage


class PolarsMetricsStorage(MetricsStorage):
    """Polars/PyArrow-based metrics storage with WAL for concurrent access.

    Write path:
    1. All writes go to WAL (JSONL) - fast, no locks
    2. When WAL exceeds threshold, archive to Parquet via Polars and clear WAL

    Read path:
    1. Read from Parquet archives (archived data) - no locks
    2. Read from WAL (recent data) - no locks
    3. Merge and return sorted results

    This design allows:
    - Writer and Reader to coexist without lock contention
    - Fast writes (JSONL append is very fast)
    - Efficient queries on large datasets (Parquet via Polars)
    - Direct Parquet manipulation without SQL overhead
    """

    def __init__(
        self,
        base_dir: str | Path,
        project_name: str,
        run_name: str,
        archive_threshold_bytes: int = 1 * 1024 * 1024,
    ) -> None:
        """Initialize Parquet storage.

        Args:
            base_dir: Base directory for data storage
            project_name: Project name
            run_name: Run name
            archive_threshold_bytes: WAL size threshold to trigger archiving (default: 1MB)
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True, parents=True)
        self.project_name = project_name
        self.run_name = run_name
        self._archive_threshold = archive_threshold_bytes

    def _get_wal_path(self) -> Path:
        """Get WAL file path for this run."""
        project_dir = self.base_dir / self.project_name
        project_dir.mkdir(exist_ok=True, parents=True)
        return project_dir / f"{self.run_name}.wal.jsonl"

    def _get_archive_path(self) -> Path:
        """Get archive directory path for this run."""
        return self.base_dir / self.project_name / f"{self.run_name}_archive"

    def _write_to_wal(self, wal_path: Path, data: dict[str, Any]) -> None:
        """Write data to WAL with fdatasync for durability.

        Uses secure_open_append to ensure file is created with 0o600 permissions.
        """
        with secure_open_append(wal_path) as f:
            f.write(json.dumps(data) + "\n")
            f.flush()
            datasync(f.fileno())

    def _read_wal(self, wal_path: Path) -> list[dict[str, Any]]:
        """Read all records from WAL."""
        records = []
        if wal_path.exists():
            with open(wal_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return records

    def _parse_timestamp(self, ts: int | str) -> datetime:
        """Parse timestamp from UNIX milliseconds (int) or ISO 8601 (str).

        Args:
            ts: Timestamp as UNIX milliseconds (int) or ISO 8601 string

        Returns:
            datetime: Parsed datetime object
        """
        if isinstance(ts, int):
            return datetime.fromtimestamp(ts / 1000.0)
        return datetime.fromisoformat(ts)

    def _create_long_dataframe(self, rows: list[dict[str, Any]]) -> pl.DataFrame:
        """Create a long-format DataFrame from row data.

        Args:
            rows: List of dicts with keys: timestamp, step, metric_name, metric_value

        Returns:
            Polars DataFrame with schema:
            - timestamp: Datetime
            - step: Int64
            - metric_name: Utf8
            - metric_value: Float64
        """
        return pl.DataFrame(
            rows,
            schema={
                "timestamp": pl.Datetime,
                "step": pl.Int64,
                "metric_name": pl.Utf8,
                "metric_value": pl.Float64,
            },
        )

    def _pivot_to_wide(self, df_long: pl.DataFrame) -> pl.DataFrame:
        """Pivot a long-format DataFrame to wide format.

        Args:
            df_long: DataFrame with columns: timestamp, step, metric_name, metric_value

        Returns:
            DataFrame with columns: timestamp, step, and one column per metric
        """
        return df_long.pivot(
            values="metric_value",
            index=["timestamp", "step"],
            on="metric_name",
            aggregate_function="first",
        ).sort(["timestamp", "step"])

    def _expand_metrics_to_rows(
        self,
        records: list[dict[str, Any]],
        metric_names: list[str] | None = None,
        prefix_underscore: bool = False,
    ) -> list[dict[str, Any]]:
        """Expand WAL records into long-format rows.

        Args:
            records: List of WAL records with keys: timestamp, step, metrics
            metric_names: Optional list of metric names to filter by
            prefix_underscore: If True, prefix metric names with underscore

        Returns:
            List of row dicts with keys: timestamp, step, metric_name, metric_value
        """
        rows: list[dict[str, Any]] = []
        for data in records:
            timestamp = self._parse_timestamp(data["timestamp"])
            step = data["step"]
            metrics_dict = data.get("metrics", {})

            # Filter by metric names if specified
            if metric_names is not None:
                metrics_dict = {k: v for k, v in metrics_dict.items() if k in metric_names}

            for metric_name, metric_value in metrics_dict.items():
                # Skip non-numeric values (metrics should always be numeric)
                try:
                    numeric_value = float(metric_value)
                    name = f"_{metric_name}" if prefix_underscore else metric_name
                    rows.append({
                        "timestamp": timestamp,
                        "step": step,
                        "metric_name": name,
                        "metric_value": numeric_value,
                    })
                except (ValueError, TypeError):
                    # Skip non-numeric values
                    pass

        return rows

    def _read_existing_parquet_data(self, archive_path: Path) -> pl.DataFrame | None:
        """Read existing Parquet data from latest date partition.

        Args:
            archive_path: Path to the archive directory

        Returns:
            DataFrame with existing data, or None if no data exists
        """
        date_dirs = [d for d in archive_path.iterdir() if d.is_dir() and d.name.startswith("date=")]

        if not date_dirs:
            return None

        # Get the latest date
        latest_date_str = max(d.name.split("=")[1] for d in date_dirs)
        latest_date_dir = archive_path / f"date={latest_date_str}"

        # Read existing Parquet files from latest date
        parquet_files = list(latest_date_dir.glob("*.parquet"))
        if not parquet_files:
            return None

        return pl.read_parquet(latest_date_dir / "*.parquet")

    def _add_date_partition(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add date column for partitioning based on timestamp.

        Args:
            df: DataFrame with timestamp column

        Returns:
            DataFrame with added date column
        """
        return df.with_columns(pl.col("timestamp").cast(pl.Date).alias("date"))

    def _write_partitioned_parquet(self, df: pl.DataFrame, archive_path: Path) -> None:
        """Write DataFrame to Parquet with date-based partitioning.

        Args:
            df: DataFrame with date column
            archive_path: Path to the archive directory
        """
        df.write_parquet(
            archive_path,
            compression="zstd",
            compression_level=1,
            partition_by="date",
        )

    def _clear_wal(self, wal_path: Path) -> None:
        """Clear WAL by truncating.

        Args:
            wal_path: Path to the WAL file
        """
        with open(wal_path, "w") as f:
            f.truncate(0)
            f.flush()
            datasync(f.fileno())

    def _load_from_parquet(
        self,
        archive_path: Path,
        metric_names: list[str] | None = None,
    ) -> pl.DataFrame | None:
        """Load metrics from Parquet archives in wide format.

        Args:
            archive_path: Path to the archive directory
            metric_names: Optional list of metric names to filter by

        Returns:
            DataFrame in wide format, or None if no data exists
        """
        if not archive_path.exists():
            return None

        try:
            # Read all Parquet files (columns: timestamp, step, metric_name, metric_value, date)
            df_long = pl.read_parquet(archive_path / "**" / "*.parquet")

            # Filter by metric names if specified
            if metric_names is not None:
                df_long = df_long.filter(pl.col("metric_name").is_in(metric_names))

            # Add underscore prefix to metric names
            df_long = df_long.with_columns(pl.concat_str([pl.lit("_"), pl.col("metric_name")]).alias("metric_name"))

            return self._pivot_to_wide(df_long)
        except Exception:
            # If no parquet files exist yet, that's okay
            return None

    def _load_from_wal(
        self,
        wal_path: Path,
        metric_names: list[str] | None = None,
    ) -> pl.DataFrame | None:
        """Load metrics from WAL in wide format.

        Args:
            wal_path: Path to the WAL file
            metric_names: Optional list of metric names to filter by

        Returns:
            DataFrame in wide format, or None if no data exists
        """
        wal_records = self._read_wal(wal_path)
        if not wal_records:
            return None

        rows = self._expand_metrics_to_rows(wal_records, metric_names=metric_names, prefix_underscore=True)
        if not rows:
            return None

        df_long = self._create_long_dataframe(rows)
        return self._pivot_to_wide(df_long)

    def _combine_dataframes(self, dfs: list[pl.DataFrame]) -> pl.DataFrame:
        """Combine multiple DataFrames into one sorted DataFrame.

        Args:
            dfs: List of DataFrames to combine

        Returns:
            Combined and sorted DataFrame
        """
        if not dfs:
            # Return empty DataFrame with correct schema
            return pl.DataFrame(
                schema={
                    "timestamp": pl.Datetime,
                    "step": pl.Int64,
                }
            )

        if len(dfs) == 1:
            return dfs[0]

        # Concatenate and handle overlapping columns
        return pl.concat(dfs, how="diagonal").sort(["timestamp", "step"])

    def _try_archive(self) -> bool:
        """Try to archive WAL to Parquet via Polars.

        Returns:
            bool: True if archive succeeded
        """
        wal_path = self._get_wal_path()

        try:
            records = self._read_wal(wal_path)
            if not records:
                return True

            archive_path = self._get_archive_path()
            archive_path.mkdir(exist_ok=True, parents=True)

            # Load existing data from latest date partition
            existing_df = self._read_existing_parquet_data(archive_path)

            # Convert WAL records to DataFrame
            rows = self._expand_metrics_to_rows(records)
            new_df = self._create_long_dataframe(rows)
            new_df = self._add_date_partition(new_df)

            # Combine existing and new data
            combined_df = pl.concat([existing_df, new_df]) if existing_df is not None else new_df

            # Write and clear WAL
            self._write_partitioned_parquet(combined_df, archive_path)
            self._clear_wal(wal_path)
            return True

        except Exception as e:  # pragma: no cover - best-effort logging
            logger.warning(f"Archive failed for {self.project_name}/{self.run_name}: {e}")
            return False

    def save(self, metrics_data: dict[str, Any]) -> str:
        """Save metrics to WAL.

        Args:
            metrics_data: Metrics data to save

        Returns:
            str: Empty string
        """
        wal_path = self._get_wal_path()

        # Check if archiving is needed BEFORE writing
        if wal_path.exists() and wal_path.stat().st_size >= self._archive_threshold:
            self._try_archive()

        try:
            self._write_to_wal(wal_path, metrics_data)
        except OSError as e:  # pragma: no cover - error path
            raise RuntimeError(f"Failed to write to WAL: {e}") from e

        return ""

    def load(
        self,
        metric_names: list[str] | None = None,
    ) -> pl.DataFrame:
        """Load metrics from Parquet archives + WAL in wide format.

        Args:
            metric_names: Optional list of metric names to filter by

        Returns:
            Polars DataFrame in wide format with columns:
            - timestamp: Datetime
            - step: Int64
            - _<metric_name>: Float64 for each metric (underscore-prefixed)

        Raises:
            RunNotFoundError: If the run does not exist
        """
        wal_path = self._get_wal_path()
        archive_path = self._get_archive_path()

        if not wal_path.exists() and not archive_path.exists():
            raise RunNotFoundError(f"Run '{self.run_name}' not found in project '{self.project_name}'")

        dfs_to_concat: list[pl.DataFrame] = []

        # Load from Parquet archives
        df_parquet = self._load_from_parquet(archive_path, metric_names)
        if df_parquet is not None:
            dfs_to_concat.append(df_parquet)

        # Load from WAL
        df_wal = self._load_from_wal(wal_path, metric_names)
        if df_wal is not None:
            dfs_to_concat.append(df_wal)

        return self._combine_dataframes(dfs_to_concat)

    def finish(self) -> None:
        """Flush WAL to Parquet archive.

        Force archive any remaining WAL data to Parquet, regardless of threshold.
        This ensures all metrics are persisted in Parquet format when the run completes.
        """
        wal_path = self._get_wal_path()
        if wal_path.exists() and wal_path.stat().st_size > 0:
            self._try_archive()

    def close(self) -> None:
        """Close storage backend.

        This backend doesn't hold long-lived connections, so this is a no-op.
        """
        pass
