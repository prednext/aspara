"""
ProjectMetadataStorage - Project-level metadata storage.

This module provides storage for project metadata (notes, tags, timestamps)
used by the catalog and dashboard layers.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from aspara.logger import logger
from aspara.utils.validators import validate_name, validate_safe_path

from .base import BaseMetadataStorage


class ProjectMetadataStorage(BaseMetadataStorage):
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

    def _merge_loaded(self, loaded: dict[str, Any]) -> dict[str, Any]:
        """Normalise loaded metadata, filling missing fields with defaults."""
        return {
            "notes": loaded.get("notes", ""),
            "tags": loaded.get("tags", []),
            "created_at": loaded.get("created_at"),
            "updated_at": loaded.get("updated_at"),
        }

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
        except OSError as e:
            logger.warning(f"Failed to delete project metadata file {self._metadata_path}: {e}")
            return False
