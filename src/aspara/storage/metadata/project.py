"""
ProjectMetadataStorage - Project-level metadata storage.

This module provides storage for project metadata (notes, tags, timestamps)
used by the catalog and dashboard layers.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aspara.utils import atomic_write_json
from aspara.utils.validators import validate_name, validate_safe_path

from .models import validate_metadata


class ProjectMetadataStorage:
    """Project-level metadata storage.

    Stores project metadata in {project_name}/metadata.json files.
    This includes notes, tags, created_at, and updated_at timestamps.
    """

    def __init__(self, base_dir: str | Path, project_name: str) -> None:
        """Initialize project metadata storage.

        Args:
            base_dir: Base directory for data storage
            project_name: Project name

        Raises:
            ValueError: If project name is invalid or path is unsafe
        """
        validate_name(project_name, "project name")

        self.base_dir = Path(base_dir)
        self.project_name = project_name

        self._metadata_path = self._get_metadata_path()
        validate_safe_path(self._metadata_path, self.base_dir)

        self._metadata: dict[str, Any] = {
            "notes": "",
            "tags": [],
            "created_at": None,
            "updated_at": None,
        }
        self._load()

    def _get_metadata_path(self) -> Path:
        """Get the path to this project's metadata file.

        Returns:
            Path to the metadata.json file
        """
        return self.base_dir / self.project_name / "metadata.json"

    def _load(self) -> None:
        """Load existing metadata from file if it exists.

        Uses try/except pattern instead of exists() check to avoid TOCTOU race condition.
        """
        try:
            with open(self._metadata_path, encoding="utf-8") as f:
                loaded_metadata = json.load(f)

            self._metadata = {
                "notes": loaded_metadata.get("notes", ""),
                "tags": loaded_metadata.get("tags", []),
                "created_at": loaded_metadata.get("created_at"),
                "updated_at": loaded_metadata.get("updated_at"),
            }
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

    def get_metadata(self) -> dict[str, Any]:
        """Get all metadata.

        Returns:
            Complete metadata dictionary with notes, tags, created_at, updated_at
        """
        return dict(self._metadata)

    def update_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Update metadata.

        The metadata dict may contain partial fields (notes, tags).
        Timestamps are managed automatically.

        Args:
            metadata: Metadata dictionary with fields to update

        Returns:
            Updated metadata dictionary

        Raises:
            ValueError: If validation fails
        """
        self._validate_metadata_values(metadata)

        now = datetime.now().isoformat()

        if self._metadata["created_at"] is None:
            self._metadata["created_at"] = now

        self._metadata["updated_at"] = now

        if "notes" in metadata:
            self._metadata["notes"] = metadata["notes"]

        if "tags" in metadata:
            self._metadata["tags"] = metadata["tags"]

        self._save()
        return dict(self._metadata)

    def delete_metadata(self) -> bool:
        """Delete metadata file.

        Returns:
            True if deleted, False if it didn't exist
        """
        if not self._metadata_path.exists():
            return False

        try:
            self._metadata_path.unlink()
            self._metadata = {
                "notes": "",
                "tags": [],
                "created_at": None,
                "updated_at": None,
            }
            return True
        except OSError:
            return False

    def close(self) -> None:
        """Close storage (no-op for file-based storage)."""
        pass
