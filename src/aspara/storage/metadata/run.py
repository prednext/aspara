"""
RunMetadataStorage - Run-level metadata storage.

This module provides storage for run metadata (params, config, tags, notes, etc.)
used for experiment tracking.
"""

import json
from pathlib import Path
from typing import Any

from aspara.models import RunStatus
from aspara.utils import atomic_write_json
from aspara.utils.validators import validate_name, validate_safe_path

from .models import validate_metadata


class RunMetadataStorage:
    """Run-level metadata storage.

    Stores run metadata in {run_name}.meta.json files.
    This includes params, config, tags, notes, artifacts, summary, and other run-specific data.
    """

    def __init__(self, base_dir: str | Path, project_name: str, run_name: str) -> None:
        """Initialize run metadata storage.

        Args:
            base_dir: Base directory for data storage
            project_name: Project name
            run_name: Run name

        Raises:
            ValueError: If project/run name is invalid or path is unsafe
        """
        validate_name(project_name, "project name")
        validate_name(run_name, "run name")

        self.base_dir = Path(base_dir)
        self.project_name = project_name
        self.run_name = run_name

        self._metadata_path = self._get_metadata_path()
        validate_safe_path(self._metadata_path, self.base_dir)

        self._metadata: dict[str, Any] = {
            "run_id": None,
            "tags": [],
            "notes": "",
            "params": {},
            "config": {},
            "artifacts": [],
            "summary": {},
            "is_finished": False,
            "exit_code": None,
            "status": RunStatus.WIP.value,
            "start_time": None,
            "finish_time": None,
        }
        self._load()

    def _get_metadata_path(self) -> Path:
        """Get the path to this run's metadata file.

        Returns:
            Path to the metadata JSON file
        """
        return self.base_dir / self.project_name / f"{self.run_name}.meta.json"

    def _load(self) -> None:
        """Load existing metadata from file if it exists.

        Uses try/except pattern instead of exists() check to avoid TOCTOU race condition.
        """
        try:
            with open(self._metadata_path, encoding="utf-8") as f:
                self._metadata = json.load(f)
        except FileNotFoundError:
            # File doesn't exist yet, keep default values
            pass
        except (json.JSONDecodeError, OSError):
            # File is corrupted or unreadable, keep default values
            pass

    def _save(self) -> None:
        """Save metadata to file.

        Raises:
            ValueError: If failed to write metadata file
        """
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            atomic_write_json(self._metadata_path, self._metadata)
        except OSError as e:
            raise ValueError(f"Failed to write metadata file: {e}") from e

    def _validate_metadata_values(self, metadata: dict[str, Any]) -> None:
        """Validate notes/tags against resource limits.

        Args:
            metadata: Metadata dictionary to validate

        Raises:
            ValueError: If validation fails
        """
        validate_metadata(metadata)

    def set_init(
        self,
        run_id: str,
        tags: list[str] | None = None,
        notes: str | None = None,
        timestamp: int | None = None,
    ) -> None:
        """Set initial run metadata.

        Args:
            run_id: Unique run identifier
            tags: List of tags
            notes: Run notes/description
            timestamp: UNIX time in milliseconds (int)

        Raises:
            ValueError: If tags or notes validation fails
        """
        values_to_validate: dict[str, Any] = {}
        if tags is not None:
            values_to_validate["tags"] = tags
        if notes is not None:
            values_to_validate["notes"] = notes
        self._validate_metadata_values(values_to_validate)

        self._metadata["run_id"] = run_id
        if tags is not None:
            self._metadata["tags"] = tags
        if notes is not None:
            self._metadata["notes"] = notes
        if timestamp is not None and self._metadata["start_time"] is None:
            self._metadata["start_time"] = timestamp
        self._save()

    def update_config(self, config: dict[str, Any]) -> None:
        """Update config parameters.

        Args:
            config: Configuration dictionary to merge
        """
        self._metadata["config"].update(config)
        self._save()

    def update_params(self, params: dict[str, Any]) -> None:
        """Update parameters.

        Args:
            params: Parameters dictionary to merge
        """
        self._metadata["params"].update(params)
        self._save()

    def add_artifact(self, artifact_data: dict[str, Any]) -> None:
        """Add artifact metadata.

        Args:
            artifact_data: Artifact metadata dictionary
        """
        self._metadata["artifacts"].append(artifact_data)
        self._save()

    def update_summary(self, summary: dict[str, Any]) -> None:
        """Update summary data.

        Args:
            summary: Summary dictionary to merge
        """
        self._metadata["summary"].update(summary)
        self._save()

    def set_finish(self, exit_code: int, timestamp: int) -> None:
        """Mark run as finished.

        Args:
            exit_code: Exit code (0 = success)
            timestamp: UNIX time in milliseconds (int)
        """
        self._metadata["is_finished"] = True
        self._metadata["exit_code"] = exit_code
        self._metadata["finish_time"] = timestamp

        status = RunStatus.from_is_finished_and_exit_code(True, exit_code)
        self._metadata["status"] = status.value

        self._save()

    def set_tags(self, tags: list[str]) -> None:
        """Set tags (replaces existing tags).

        Args:
            tags: List of tags

        Raises:
            ValueError: If tags validation fails
        """
        self._validate_metadata_values({"tags": tags})
        self._metadata["tags"] = tags
        self._save()

    def get_metadata(self) -> dict[str, Any]:
        """Get all metadata.

        Returns:
            Complete metadata dictionary
        """
        return dict(self._metadata)

    def update_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Update metadata fields (notes, tags).

        Args:
            metadata: Dictionary with fields to update

        Returns:
            Updated complete metadata dictionary

        Raises:
            ValueError: If validation fails
        """
        self._validate_metadata_values(metadata)

        if "notes" in metadata:
            self._metadata["notes"] = metadata["notes"]
        if "tags" in metadata:
            self._metadata["tags"] = metadata["tags"]

        self._save()
        return dict(self._metadata)

    def delete_metadata(self) -> bool:
        """Delete metadata file.

        Returns:
            True if file was deleted, False if it didn't exist
        """
        if not self._metadata_path.exists():
            return False
        self._metadata_path.unlink()
        self._metadata = {
            "run_id": None,
            "tags": [],
            "notes": "",
            "params": {},
            "config": {},
            "artifacts": [],
            "summary": {},
            "is_finished": False,
            "exit_code": None,
            "status": RunStatus.WIP.value,
            "start_time": None,
            "finish_time": None,
        }
        return True

    def get_params(self) -> dict[str, Any]:
        """Get params and config merged.

        Returns:
            Dictionary with all params and config
        """
        result: dict[str, Any] = {}
        result.update(self._metadata.get("params", {}))
        result.update(self._metadata.get("config", {}))
        return result

    def get_artifacts(self) -> list[dict[str, Any]]:
        """Get artifact metadata list.

        Returns:
            List of artifact metadata dictionaries
        """
        return list(self._metadata.get("artifacts", []))

    def get_tags(self) -> list[str]:
        """Get tags.

        Returns:
            List of tags
        """
        return list(self._metadata.get("tags", []))

    def set_status(self, status: RunStatus) -> None:
        """Set run status.

        Args:
            status: New run status
        """
        self._metadata["status"] = status.value

        is_finished, exit_code = status.to_is_finished_and_exit_code()
        self._metadata["is_finished"] = is_finished
        self._metadata["exit_code"] = exit_code

        self._save()

    def get_status(self) -> RunStatus:
        """Get run status.

        Returns:
            Current run status
        """
        status_value = self._metadata.get("status", RunStatus.WIP.value)
        return RunStatus(status_value)

    def close(self) -> None:
        """Close storage (no-op for file-based storage)."""
        pass
