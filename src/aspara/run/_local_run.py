"""LocalRun implementation for tracking metrics to the local filesystem."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aspara.config import get_data_dir
from aspara.run._base_run import BaseRun
from aspara.run._config import Config
from aspara.run._summary import Summary
from aspara.storage.metrics import create_metrics_storage, resolve_metrics_storage_backend
from aspara.utils.metadata import update_project_metadata_tags
from aspara.utils.timestamp import parse_to_ms


class LocalRun(BaseRun):
    """A local run that stores metrics to the local filesystem."""

    def __init__(
        self,
        name: str | None = None,
        project: str | None = None,
        config: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        dir: str | None = None,
        storage_backend: str | None = None,
        project_tags: list[str] | None = None,
        resume: bool = False,
    ) -> None:
        """Initialize a new local run.

        Args:
            name: Name of the run. If None, generates a random name.
            project: Project name this run belongs to. Defaults to "default".
            config: Initial configuration parameters.
            tags: List of tags for this run.
            notes: Run notes/description (wandb-compatible).
            dir: Base directory for storing data. If None, uses XDG-based default (~/.local/share/aspara).
            storage_backend: Storage backend type ('jsonl' or 'polars'). Defaults to 'jsonl'. ASPARA_STORAGE_BACKEND has higher priority than this argument.
            project_tags: List of tags to add to the project.
            resume: If True and a run with the same name already exists, resume
                it (reuse run_id, reset finish state, continue step numbering).
                If no existing run is found, a new run is created.
        """
        super().__init__(name=name, project=project, tags=tags, notes=notes)

        # Determine data directory
        data_dir = dir or str(get_data_dir())
        self._data_dir = data_dir

        # Determine storage backend using central resolver
        resolved_backend = resolve_metrics_storage_backend(storage_backend)

        # Build path within data directory (project/run structure)
        base_dir = os.path.join(data_dir, self.project)
        self._output_path = os.path.join(base_dir, f"{self.name}.jsonl")

        # Set up artifacts directory path
        run_dir = os.path.dirname(self._output_path)
        self._artifacts_dir = os.path.join(run_dir, self.name, "artifacts")

        # Initialize metrics storage backend
        self._storage_backend_type = resolved_backend
        self._metrics_storage = create_metrics_storage(
            backend=resolved_backend,
            base_dir=data_dir,
            project_name=self.project,
            run_name=self.name,
        )

        # Initialize metadata storage
        from aspara.storage import RunMetadataStorage

        self._metadata_storage = RunMetadataStorage(
            base_dir=data_dir,
            project_name=self.project,
            run_name=self.name,
        )

        # Detect existing run by checking for a metadata file with a run_id.
        existing_meta_path = Path(base_dir) / f"{self.name}.meta.json"
        existing_run_id: str | None = None
        if existing_meta_path.exists():
            try:
                with open(existing_meta_path) as f:
                    existing_meta = json.load(f)
                existing_run_id = existing_meta.get("run_id")
            except (json.JSONDecodeError, OSError):
                existing_run_id = None

        is_resuming = resume and existing_run_id is not None

        if is_resuming:
            # Reuse the existing run_id and reset finish state.
            self.id = existing_run_id
            self._metadata_storage.reset_finish()
            # Continue step numbering from where the previous session left off.
            self._current_step = self._recover_last_step(data_dir)
        else:
            # New run: generate a fresh run_id.
            self.id = self._generate_run_id()
            if existing_run_id is not None and not resume:
                # A run with the same name already exists and the user did not
                # request a resume. Warn that new metrics will be appended.
                print(
                    f"aspara: Warning: run '{self.name}' already exists in project "
                    f"'{self.project}'. New metrics will be appended to the existing "
                    f"file. Use resume=True to continue the existing run."
                )

        self.config = Config(config, on_change=self._on_config_change)
        self.summary = Summary(on_change=self._on_summary_change)

        # Update project-level metadata tags if provided
        update_project_metadata_tags(self._data_dir, self.project, project_tags)

        # User-facing guidance: where data is stored and how to view it.
        backend_msg = f" (backend: {self._storage_backend_type})" if self._storage_backend_type == "polars" else ""
        storage_location = (
            os.path.abspath(os.path.join(base_dir, f"{self.name}.wal.jsonl")) if self._storage_backend_type == "polars" else os.path.abspath(self._output_path)
        )
        resume_msg = " (resumed)" if is_resuming else ""
        print(f"aspara: Run '{self.name}' initialized in project '{self.project}'{backend_msg}{resume_msg}")
        print(f"aspara: Data directory: {os.path.abspath(data_dir)}")
        print(f"aspara: Writing metrics to: {storage_location}")
        print("aspara: View results with: aspara dashboard")

        self._ensure_output_dir()
        self._write_init_record()

    def _recover_last_step(self, data_dir: str) -> int:
        """Recover the next step number from existing metrics.

        Reads the existing metrics file and returns ``max(step) + 1`` so that
        resumed logging continues without overwriting earlier rows. Returns 0
        when no prior metrics are present.

        Args:
            data_dir: Base data directory.

        Returns:
            Next step number to use.
        """
        try:
            df = self._metrics_storage.load()
        except Exception:
            return 0
        if df is None or len(df) == 0 or "step" not in df.columns:
            return 0
        last_step = df.select("step").to_series().max()
        if last_step is None:
            return 0
        return int(last_step) + 1

    def _write_init_record(self) -> None:
        """Write initial run record with metadata."""
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        self._metadata_storage.set_init(
            run_id=self.id,
            tags=self.tags,
            notes=self.notes,
            timestamp=timestamp,
        )

        # Write initial config if present
        if self.config._data:
            self._metadata_storage.update_config(self.config.to_dict())

    def _on_config_change(self) -> None:
        """Callback when config changes."""
        if not self._finished:
            self._metadata_storage.update_config(self.config.to_dict())

    def _on_summary_change(self) -> None:
        """Callback when summary changes."""
        if not self._finished:
            self._metadata_storage.update_summary(self.summary.to_dict())

    def log(
        self,
        data: dict[str, Any],
        step: int | None = None,
        commit: bool = True,
        timestamp: str | None = None,
    ) -> None:
        """Log metrics and other data.

        This is the main method for logging data during a run. It supports
        scalar values (int, float) for now, with future support for images,
        tables, etc.

        Args:
            data: Dictionary of metric names to values
            step: Optional step number. If None, auto-increments.
            commit: If True, commits the step. If False, accumulates data.
            timestamp: Optional timestamp in ISO format. If None, uses current time.

        Raises:
            ValueError: If data contains invalid values
            RuntimeError: If run has already finished
        """
        self._ensure_not_finished()

        # Prepare step value (mirrors previous behaviour)
        self._prepare_step(step, commit)

        # Validate and normalize metrics using shared helper
        metrics = self._validate_metrics(data)

        if metrics:
            # Generate current time if timestamp is None, otherwise parse
            if timestamp is None:
                timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            else:
                timestamp_ms = parse_to_ms(timestamp)
            metrics_data = {
                "timestamp": timestamp_ms,
                "step": self._current_step,
                "metrics": metrics,
            }
            if self._metrics_storage is not None:
                self._metrics_storage.save(metrics_data)

        self._after_log(commit)

    def log_artifact(
        self,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
    ) -> None:
        """Log an artifact file for this run.

        Args:
            file_path: Path to the file to be logged as an artifact
            name: Optional custom name for the artifact. If None, uses the filename.
            description: Optional description of the artifact
            category: Optional category ('code', 'model', 'config', 'data', 'other')

        Raises:
            ValueError: If file_path is invalid or file doesn't exist
            OSError: If file cannot be copied to artifacts directory
            RuntimeError: If run has already finished
        """
        self._ensure_not_finished()

        # Validate input using shared helper
        abs_file_path, artifact_name = self._validate_artifact_input(file_path, name, category)

        # Ensure artifacts directory exists
        os.makedirs(self._artifacts_dir, exist_ok=True)

        # Copy file to artifacts directory
        dest_path = os.path.join(self._artifacts_dir, artifact_name)
        source_size = os.path.getsize(abs_file_path)
        try:
            shutil.copy2(abs_file_path, dest_path)
        except OSError as e:
            raise OSError(f"Failed to copy artifact file: {e}") from e

        # Verify the copy succeeded by comparing file sizes. A partial copy
        # (e.g. disk full mid-write) would leave a truncated file that
        # silently passes without this check.
        dest_size = os.path.getsize(dest_path)
        if dest_size != source_size:
            # Remove the corrupted destination so a retry can start clean.
            with contextlib.suppress(OSError):
                os.remove(dest_path)
            raise OSError(f"Artifact copy verification failed: size mismatch (source={source_size}, dest={dest_size})")

        # Get file size
        file_size = dest_size

        # Log artifact metadata
        artifact_data = {
            "name": artifact_name,
            "original_path": abs_file_path,
            "stored_path": os.path.join("artifacts", artifact_name),
            "file_size": file_size,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }

        if description:
            artifact_data["description"] = description

        if category:
            artifact_data["category"] = category

        self._metadata_storage.add_artifact(artifact_data)

    def finish(self, exit_code: int = 0, quiet: bool = False, flush_timeout: float = 30.0) -> None:
        """Finish the run and write final record.

        Args:
            exit_code: Exit code for the run (0 = success)
            quiet: If True, suppress output messages
            flush_timeout: Unused — LocalRun writes synchronously so there is
                no queue to flush. Accepted for signature compatibility with
                RemoteRun.finish().
        """
        if not self._mark_finished():
            return

        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        self._metadata_storage.set_finish(exit_code=exit_code, timestamp=timestamp)

        # Finalize metrics storage (e.g., flush WAL to Parquet)
        if self._metrics_storage is not None:
            self._metrics_storage.finish()

        # Close storage backend connections
        if self._metrics_storage is not None:
            self._metrics_storage.close()
        if self._metadata_storage is not None:
            self._metadata_storage.close()

        if not quiet:
            print(f"aspara: Run '{self.name}' finished with exit code {exit_code}")
            print("aspara: View results with: aspara dashboard")

    def flush(self, timeout: float = 30.0) -> int:
        """Ensure all metrics are written to disk.

        LocalRun writes directly to disk on every ``log()`` call, so there
        is never any buffered data to flush. This method always returns 0
        (no failures) for API compatibility with ``RemoteRun.flush()``.

        Args:
            timeout: Ignored. Accepted for API compatibility with
                ``RemoteRun.flush()``.

        Returns:
            Number of metrics that failed to persist (always 0 for local runs).
        """
        # Currently a no-op as we're writing directly to file
        # This method exists for API compatibility and future buffering support
        return 0

    def _ensure_output_dir(self) -> None:
        """Ensure the output directory exists."""
        output_dir = os.path.dirname(self._output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Touch the file to ensure it exists and is writable
        Path(self._output_path).touch()

    def set_tags(self, tags: list[str]) -> None:
        """Set tags for this run.

        Args:
            tags: List of tags

        Raises:
            RuntimeError: If run has already finished
        """
        if self._finished:
            raise RuntimeError("Cannot modify a finished run")

        self.tags = tags
        self._metadata_storage.set_tags(tags)
