"""
ProjectCatalog - Catalog for discovering and managing projects.

This module provides functionality for listing, getting, and deleting projects
in the data directory.
"""

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from aspara.exceptions import ProjectNotFoundError
from aspara.storage import ProjectMetadataStorage
from aspara.utils.validators import validate_name, validate_safe_path

logger = logging.getLogger(__name__)


class ProjectInfo(BaseModel):
    """Project information."""

    name: str
    run_count: int
    last_update: datetime


# Run data file suffixes used when discovering and counting runs.
_RUN_DATA_SUFFIXES = (".jsonl", ".db", ".wal")
_RUN_EXCLUDED_SUFFIXES = (".wal.jsonl", ".meta.jsonl")


class ProjectCatalog:
    """Catalog for discovering and managing projects.

    This class provides methods to list, get, and delete projects
    in the data directory. It does not handle metrics data directly;
    that responsibility belongs to MetricsStorage.
    """

    def __init__(self, data_dir: str | Path) -> None:
        """Initialize the project catalog.

        Args:
            data_dir: Base directory for data storage
        """
        self.data_dir = Path(data_dir)

    def _scan_projects(self, *, include_metadata: bool = False) -> list[tuple[ProjectInfo, dict[str, Any] | None]]:
        """Scan the data directory and build project information.

        Args:
            include_metadata: Whether to load project metadata.json during the scan.

        Returns:
            List of (ProjectInfo, metadata) tuples. ``metadata`` is ``None`` when
            ``include_metadata`` is ``False``.
        """
        results: list[tuple[ProjectInfo, dict[str, Any] | None]] = []
        if not self.data_dir.exists():
            return results

        try:
            # Use scandir for efficient iteration with cached stat info
            with os.scandir(self.data_dir) as project_entries:
                for project_entry in project_entries:
                    if not project_entry.is_dir():
                        continue

                    # Skip hidden/reserved directories (e.g. .queue)
                    if project_entry.name.startswith("."):
                        continue

                    # Collect run files and optionally metadata in a single pass
                    run_files_mtime: list[float] = []
                    metadata: dict[str, Any] | None = None
                    with os.scandir(project_entry.path) as file_entries:
                        for file_entry in file_entries:
                            if include_metadata and file_entry.name == "metadata.json":
                                metadata = ProjectMetadataStorage.load_metadata_file(Path(file_entry.path))
                            elif file_entry.name.endswith(_RUN_DATA_SUFFIXES) and not file_entry.name.endswith(_RUN_EXCLUDED_SUFFIXES):
                                # stat() result is cached by scandir
                                run_files_mtime.append(file_entry.stat().st_mtime)

                    if include_metadata and metadata is None:
                        metadata = ProjectMetadataStorage.default_metadata()

                    run_count = len(run_files_mtime)

                    # Find last update time - use cached stat from scandir
                    if run_files_mtime:
                        last_update = datetime.fromtimestamp(max(run_files_mtime), tz=timezone.utc)
                    else:
                        last_update = datetime.fromtimestamp(project_entry.stat().st_mtime, tz=timezone.utc)

                    results.append((
                        ProjectInfo(
                            name=project_entry.name,
                            run_count=run_count,
                            last_update=last_update,
                        ),
                        metadata,
                    ))
        except (OSError, PermissionError):
            pass

        return sorted(results, key=lambda item: item[0].name)

    def get_projects(self) -> list[ProjectInfo]:
        """List all projects in the data directory.

        Uses os.scandir() for efficient directory iteration with cached stat info.

        Returns:
            List of ProjectInfo objects sorted by name
        """
        return [project for project, _ in self._scan_projects(include_metadata=False)]

    def get_projects_with_metadata(self) -> list[tuple[ProjectInfo, dict[str, Any]]]:
        """List all projects with their metadata in a single directory pass.

        Returns:
            List of (ProjectInfo, metadata) tuples sorted by project name.
        """
        return [(project, metadata) for project, metadata in self._scan_projects(include_metadata=True) if metadata is not None]

    def get(self, name: str) -> ProjectInfo:
        """Get a specific project by name.

        Args:
            name: Project name

        Returns:
            ProjectInfo object

        Raises:
            ValueError: If project name is invalid
            ProjectNotFoundError: If project does not exist
        """
        validate_name(name, "project name")

        project_dir = self.data_dir / name
        validate_safe_path(project_dir, self.data_dir)

        if not project_dir.exists() or not project_dir.is_dir():
            raise ProjectNotFoundError(f"Project '{name}' not found")

        # Count runs and collect mtimes in a single scandir pass, using the same
        # suffix logic as get_projects() for consistency and reduced I/O.
        run_files_mtime: list[float] = []
        try:
            with os.scandir(project_dir) as file_entries:
                for file_entry in file_entries:
                    if file_entry.name.endswith(_RUN_DATA_SUFFIXES) and not file_entry.name.endswith(_RUN_EXCLUDED_SUFFIXES):
                        run_files_mtime.append(file_entry.stat().st_mtime)
        except (OSError, PermissionError):
            pass

        run_count = len(run_files_mtime)

        # Get last update time from run files
        last_update = datetime.fromtimestamp(project_dir.stat().st_mtime, tz=timezone.utc)
        if run_files_mtime:
            last_update = datetime.fromtimestamp(max(run_files_mtime), tz=timezone.utc)

        return ProjectInfo(
            name=name,
            run_count=run_count,
            last_update=last_update,
        )

    def exists(self, name: str) -> bool:
        """Check if a project exists.

        Args:
            name: Project name

        Returns:
            True if project exists, False otherwise
        """
        try:
            validate_name(name, "project name")
            project_dir = self.data_dir / name
            validate_safe_path(project_dir, self.data_dir)
            return project_dir.exists() and project_dir.is_dir()
        except ValueError:
            return False

    def delete(self, name: str) -> None:
        """Delete a project and all its runs.

        Args:
            name: Project name to delete

        Raises:
            ValueError: If project name is empty or invalid
            ProjectNotFoundError: If project does not exist
            PermissionError: If deletion is not permitted
        """
        if not name:
            raise ValueError("Project name cannot be empty")

        validate_name(name, "project name")

        project_dir = self.data_dir / name
        validate_safe_path(project_dir, self.data_dir)

        if not project_dir.exists():
            raise ProjectNotFoundError(f"Project '{name}' does not exist")

        try:
            shutil.rmtree(project_dir)
            logger.info(f"Successfully deleted project: {name}")
        except (PermissionError, OSError) as e:
            logger.error(f"Error deleting project {name}: {type(e).__name__}")
            raise

    def get_metadata(self, name: str) -> dict[str, Any]:
        """Get project-level metadata.json for a project.

        Returns a dictionary with notes, tags, created_at, updated_at fields.
        """
        storage = ProjectMetadataStorage(self.data_dir, name)
        return storage.get_metadata()

    def update_metadata(self, name: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Update project-level metadata.json for a project.

        The metadata dict may contain partial fields (notes, tags).
        Validation and timestamp handling is delegated to ProjectMetadataStorage.
        """
        storage = ProjectMetadataStorage(self.data_dir, name)
        return storage.update_metadata(metadata)

    def delete_metadata(self, name: str) -> bool:
        """Delete project-level metadata.json for a project."""
        storage = ProjectMetadataStorage(self.data_dir, name)
        return storage.delete_metadata()
