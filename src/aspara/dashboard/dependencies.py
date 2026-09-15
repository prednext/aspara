"""
FastAPI dependency injection for Aspara Dashboard.

This module provides reusable dependencies for:
- Catalog instance management (ProjectCatalog, RunCatalog)
- Path parameter validation (project names, run names)
"""

from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi import Path as PathParam

from aspara.catalog import LibsqlCatalog, ProjectCatalog, RunCatalog
from aspara.catalog.libsql_adapters import LibsqlProjectCatalog, LibsqlRunCatalog
from aspara.storage.artifacts import FilesystemArtifactStore
from aspara.tenancy import (
    DEFAULT_TENANT,
    LibsqlTenant,
    configure_data_dir,
    configure_libsql_tenant_resolver,
    configure_tenant_resolver,
    register_config_change_callback,
    resolve_artifact_base_dir,
    resolve_data_dir,
    resolve_libsql_tenant,
)
from aspara.utils import validators

# Re-exported for backward compatibility; tenant resolution now lives in
# ``aspara.tenancy`` so the tracker (write path) and dashboard (read path) share
# one source of truth. ``configure_*`` are re-exported so existing callers keep
# importing them from here.
__all__ = [
    "DEFAULT_TENANT",
    "LibsqlTenant",
    "configure_data_dir",
    "configure_tenant_resolver",
    "configure_libsql_tenant_resolver",
    "ProjectCatalogLike",
    "RunCatalogLike",
    "ProjectCatalogDep",
    "RunCatalogDep",
    "DataDirDep",
    "ValidatedProject",
    "ValidatedRun",
]

# The two catalog dependencies can be served by either the file-based catalogs or
# their libSQL-backed facades, depending on how the request's tenant resolves.
ProjectCatalogLike = ProjectCatalog | LibsqlProjectCatalog
RunCatalogLike = RunCatalog | LibsqlRunCatalog


@lru_cache(maxsize=32)
def _catalogs_for_dir(data_dir: str) -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Build and cache catalog instances for a data directory (keyed per tenant)."""
    path = Path(data_dir)
    return ProjectCatalog(str(path)), RunCatalog(str(path)), path


@lru_cache(maxsize=32)
def _libsql_catalogs_for_key(
    base_dir: str | None,
    database: str | None,
    auth_token: str | None,
) -> tuple[LibsqlProjectCatalog, LibsqlRunCatalog, Path]:
    """Build and cache libSQL-backed catalog facades for one tenant database.

    The shared ``LibsqlCatalog`` (and its connection) is kept alive by this cache
    for the tenant's lifetime; a single re-entrant lock serializes access.
    """
    catalog = LibsqlCatalog(base_dir=base_dir, database=database, auth_token=auth_token)
    lock = threading.RLock()
    # Local libSQL tenants pin artifact bytes under ``base_dir``; remote tenants
    # (a database URL) do not, so delete/ZIP must not touch a shared data_dir.
    artifact_store = (
        FilesystemArtifactStore(base_dir) if base_dir and not (database or "").strip() else None
    )
    data_dir = Path(base_dir) if base_dir else Path(".")
    return (
        LibsqlProjectCatalog(catalog, lock, artifact_store),
        LibsqlRunCatalog(catalog, lock, artifact_store),
        data_dir,
    )


def _tenant_id_from_request(request: Request | None) -> str:
    """Read the tenant id set on the request state, defaulting to DEFAULT_TENANT."""
    if request is not None:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return str(tenant_id)
    return DEFAULT_TENANT


def _catalogs_for_request(request: Request | None) -> tuple[ProjectCatalogLike, RunCatalogLike, Path]:
    """Resolve the catalogs for the request's tenant.

    A libSQL tenant (when a libSQL resolver is installed and returns a spec) is
    served by the libSQL-backed facades; otherwise the file-based catalogs are
    used, exactly as before.
    """
    tenant_id = _tenant_id_from_request(request)

    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        return _libsql_catalogs_for_key(spec.base_dir, spec.database, spec.auth_token)

    data_dir = resolve_data_dir(tenant_id)
    return _catalogs_for_dir(str(data_dir))


def _get_catalogs() -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Backward-compatible accessor for the default tenant's (filesystem) catalogs."""
    return _catalogs_for_dir(str(resolve_data_dir(DEFAULT_TENANT)))


def get_project_catalog(request: Request) -> ProjectCatalogLike:
    """Get the project catalog for the request's tenant."""
    return _catalogs_for_request(request)[0]


def get_run_catalog(request: Request) -> RunCatalogLike:
    """Get the run catalog for the request's tenant."""
    return _catalogs_for_request(request)[1]


def get_data_dir_path(request: Request) -> Path:
    """Get the local artifact-bytes directory for the request's tenant.

    Remote libSQL tenants do not store artifact bytes locally, so this raises
    404 and the ZIP route never falls back to the shared default data_dir.
    """
    tenant_id = _tenant_id_from_request(request)
    root = resolve_artifact_base_dir(tenant_id)
    if root is None:
        raise HTTPException(status_code=404, detail="No artifacts found for this run")
    return root


def _clear_catalog_caches() -> None:
    """Drop all cached catalog instances (file-based and libSQL-backed)."""
    _catalogs_for_dir.cache_clear()
    _libsql_catalogs_for_key.cache_clear()


# Invalidate cached catalogs whenever the tenant resolver configuration changes.
register_config_change_callback(_clear_catalog_caches)


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
ProjectCatalogDep = Annotated[ProjectCatalogLike, Depends(get_project_catalog)]
RunCatalogDep = Annotated[RunCatalogLike, Depends(get_run_catalog)]
DataDirDep = Annotated[Path, Depends(get_data_dir_path)]
