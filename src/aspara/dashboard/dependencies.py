"""
FastAPI dependency injection for Aspara Dashboard.

This module provides reusable dependencies for:
- Catalog instance management (ProjectCatalog, RunCatalog)
- Path parameter validation (project names, run names)
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi import Path as PathParam

from aspara.catalog import ProjectCatalog, RunCatalog
from aspara.config import get_data_dir
from aspara.utils import validators

# Tenant id used when no tenant is resolved from the request (single-tenant default).
DEFAULT_TENANT = "default"

# Mutable container for the single configured data directory (single-tenant default).
_custom_data_dir: list[str | None] = [None]

# Optional tenant resolver: tenant_id -> data directory. When unset, every request
# uses the single configured data directory, i.e. behavior is identical to the
# pre-multi-tenant dashboard. Multi-tenant serving installs a resolver via
# configure_tenant_resolver() that maps each tenant to its own data location.
_tenant_resolver: list[Callable[[str], str | Path] | None] = [None]


@lru_cache(maxsize=32)
def _catalogs_for_dir(data_dir: str) -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Build and cache catalog instances for a data directory (keyed per tenant)."""
    path = Path(data_dir)
    return ProjectCatalog(str(path)), RunCatalog(str(path)), path


def _resolve_data_dir(tenant_id: str) -> Path:
    """Resolve a tenant id to its data directory.

    Uses the configured tenant resolver when present; otherwise falls back to the
    single configured data directory (single-tenant behavior).
    """
    resolver = _tenant_resolver[0]
    if resolver is not None:
        return Path(resolver(tenant_id))
    if _custom_data_dir[0] is not None:
        return Path(_custom_data_dir[0])
    return Path(get_data_dir())


def _tenant_id_from_request(request: Request | None) -> str:
    """Read the tenant id set on the request state, defaulting to DEFAULT_TENANT."""
    if request is not None:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return str(tenant_id)
    return DEFAULT_TENANT


def _catalogs_for_request(request: Request | None) -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Resolve the catalogs for the request's tenant."""
    data_dir = _resolve_data_dir(_tenant_id_from_request(request))
    return _catalogs_for_dir(str(data_dir))


def _get_catalogs() -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Backward-compatible accessor for the default tenant's catalogs."""
    return _catalogs_for_dir(str(_resolve_data_dir(DEFAULT_TENANT)))


def get_project_catalog(request: Request) -> ProjectCatalog:
    """Get the ProjectCatalog for the request's tenant."""
    return _catalogs_for_request(request)[0]


def get_run_catalog(request: Request) -> RunCatalog:
    """Get the RunCatalog for the request's tenant."""
    return _catalogs_for_request(request)[1]


def get_data_dir_path(request: Request) -> Path:
    """Get the data directory for the request's tenant."""
    return _catalogs_for_request(request)[2]


def configure_data_dir(data_dir: str | None = None) -> None:
    """Configure the single (default-tenant) data directory and clear caches.

    Args:
        data_dir: Custom data directory path. If None, uses the default.
    """
    _catalogs_for_dir.cache_clear()
    _custom_data_dir[0] = data_dir


def configure_tenant_resolver(resolver: Callable[[str], str | Path] | None) -> None:
    """Install (or clear) the tenant -> data directory resolver.

    Passing None restores single-tenant behavior (the configured data directory).
    This is the seam the multi-tenant SaaS path uses to map each tenant to its own
    data location (e.g. a per-tenant directory or, later, a libSQL database).
    """
    _catalogs_for_dir.cache_clear()
    _tenant_resolver[0] = resolver


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
