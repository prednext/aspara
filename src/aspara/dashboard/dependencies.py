"""
FastAPI dependency injection for Aspara Dashboard.

This module provides reusable dependencies for:
- Catalog instance management (ProjectCatalog, RunCatalog)
- Path parameter validation (project names, run names)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi import Path as PathParam

from aspara.catalog import ProjectCatalog, RunCatalog
from aspara.config import get_data_dir
from aspara.utils import validators

# Mutable container for custom data directory configuration
_custom_data_dir: list[str | None] = [None]


def _get_catalogs() -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Get or create catalog instances.

    Returns:
        Tuple of (ProjectCatalog, RunCatalog, data_dir Path)
    """
    if _custom_data_dir[0] is not None:
        data_dir = Path(_custom_data_dir[0])
    else:
        data_dir = Path(get_data_dir())
    return ProjectCatalog(str(data_dir)), RunCatalog(str(data_dir)), data_dir


# Cached version for performance
@lru_cache(maxsize=1)
def _get_cached_catalogs() -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Get cached catalog instances."""
    return _get_catalogs()


def get_project_catalog() -> ProjectCatalog:
    """Get the ProjectCatalog singleton instance."""
    return _get_cached_catalogs()[0]


def get_run_catalog() -> RunCatalog:
    """Get the RunCatalog singleton instance."""
    return _get_cached_catalogs()[1]


def get_data_dir_path() -> Path:
    """Get the data directory path."""
    return _get_cached_catalogs()[2]


def configure_data_dir(data_dir: str | None = None) -> None:
    """Configure data directory and reinitialize catalogs.

    This function clears the cached catalogs and reinitializes them
    with the specified data directory.

    Args:
        data_dir: Custom data directory path. If None, uses default.
    """
    # Clear the cache to force reinitialization
    _get_cached_catalogs.cache_clear()

    # Set custom data directory
    _custom_data_dir[0] = data_dir


def get_validated_project(project: Annotated[str, PathParam(description="Project name")]) -> str:
    """Validate project name path parameter.

    Args:
        project: Project name from URL path.

    Returns:
        Validated project name.

    Raises:
        HTTPException: 400 if project name is invalid.
    """
    try:
        validators.validate_project_name(project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return project


def get_validated_run(run: Annotated[str, PathParam(description="Run name")]) -> str:
    """Validate run name path parameter.

    Args:
        run: Run name from URL path.

    Returns:
        Validated run name.

    Raises:
        HTTPException: 400 if run name is invalid.
    """
    try:
        validators.validate_run_name(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return run


# Type aliases for dependency injection
ValidatedProject = Annotated[str, Depends(get_validated_project)]
ValidatedRun = Annotated[str, Depends(get_validated_run)]
ProjectCatalogDep = Annotated[ProjectCatalog, Depends(get_project_catalog)]
RunCatalogDep = Annotated[RunCatalog, Depends(get_run_catalog)]
DataDirDep = Annotated[Path, Depends(get_data_dir_path)]
