"""
FastAPI dependency injection for Aspara Dashboard.

This module provides reusable dependencies for:
- Catalog instance management (ProjectCatalog, RunCatalog)
- Path parameter validation (project names, run names)
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi import Path as PathParam

from aspara.catalog import LibsqlCatalog, ProjectCatalog, RunCatalog
from aspara.catalog.libsql_adapters import LibsqlProjectCatalog, LibsqlRunCatalog
from aspara.config import get_data_dir
from aspara.utils import validators

# The two catalog dependencies can be served by either the file-based catalogs or
# their libSQL-backed facades, depending on how the request's tenant resolves.
ProjectCatalogLike = ProjectCatalog | LibsqlProjectCatalog
RunCatalogLike = RunCatalog | LibsqlRunCatalog

# Tenant id used when no tenant is resolved from the request (single-tenant default).
DEFAULT_TENANT = "default"

# Mutable container for the single configured data directory (single-tenant default).
_custom_data_dir: list[str | None] = [None]

# Optional tenant resolver: tenant_id -> data directory. When unset, every request
# uses the single configured data directory, i.e. behavior is identical to the
# pre-multi-tenant dashboard. Multi-tenant serving installs a resolver via
# configure_tenant_resolver() that maps each tenant to its own data location.
_tenant_resolver: list[Callable[[str], str | Path] | None] = [None]


@dataclass(frozen=True)
class LibsqlTenant:
    """Connection spec for a libSQL-backed tenant.

    Either ``base_dir`` (a local ``{base_dir}/aspara.db`` file) or ``database``
    (a remote ``libsql://`` URL, with an optional ``auth_token``) identifies the
    tenant's single database.
    """

    base_dir: str | None = None
    database: str | None = None
    auth_token: str | None = None


# Optional libSQL tenant resolver: tenant_id -> LibsqlTenant | None. When it
# returns a spec, that tenant is served from its libSQL database instead of the
# filesystem. Returning None (or leaving this unset) falls back to the file-based
# path resolution, so filesystem tenants are entirely unaffected.
_libsql_resolver: list[Callable[[str], LibsqlTenant | None] | None] = [None]


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
    # A local libSQL tenant has a real directory (used only by the artifact-ZIP
    # route, which will simply 404 when no artifacts dir exists); a remote tenant
    # has none, so point at a sentinel path that never resolves.
    data_dir = Path(base_dir) if base_dir else Path("__aspara_libsql_no_local_dir__")
    return LibsqlProjectCatalog(catalog, lock), LibsqlRunCatalog(catalog, lock), data_dir


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


def _catalogs_for_request(request: Request | None) -> tuple[ProjectCatalogLike, RunCatalogLike, Path]:
    """Resolve the catalogs for the request's tenant.

    A libSQL tenant (when a libSQL resolver is installed and returns a spec) is
    served by the libSQL-backed facades; otherwise the file-based catalogs are
    used, exactly as before.
    """
    tenant_id = _tenant_id_from_request(request)

    resolver = _libsql_resolver[0]
    if resolver is not None:
        spec = resolver(tenant_id)
        if spec is not None:
            return _libsql_catalogs_for_key(spec.base_dir, spec.database, spec.auth_token)

    data_dir = _resolve_data_dir(tenant_id)
    return _catalogs_for_dir(str(data_dir))


def _get_catalogs() -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Backward-compatible accessor for the default tenant's (filesystem) catalogs."""
    return _catalogs_for_dir(str(_resolve_data_dir(DEFAULT_TENANT)))


def get_project_catalog(request: Request) -> ProjectCatalogLike:
    """Get the project catalog for the request's tenant."""
    return _catalogs_for_request(request)[0]


def get_run_catalog(request: Request) -> RunCatalogLike:
    """Get the run catalog for the request's tenant."""
    return _catalogs_for_request(request)[1]


def get_data_dir_path(request: Request) -> Path:
    """Get the data directory for the request's tenant."""
    return _catalogs_for_request(request)[2]


def _clear_catalog_caches() -> None:
    """Drop all cached catalog instances (file-based and libSQL-backed)."""
    _catalogs_for_dir.cache_clear()
    _libsql_catalogs_for_key.cache_clear()


def configure_data_dir(data_dir: str | None = None) -> None:
    """Configure the single (default-tenant) data directory and clear caches.

    Args:
        data_dir: Custom data directory path. If None, uses the default.
    """
    _clear_catalog_caches()
    _custom_data_dir[0] = data_dir


def configure_tenant_resolver(resolver: Callable[[str], str | Path] | None) -> None:
    """Install (or clear) the tenant -> data directory resolver.

    Passing None restores single-tenant behavior (the configured data directory).
    This is the seam the multi-tenant SaaS path uses to map each tenant to its own
    filesystem data location.
    """
    _clear_catalog_caches()
    _tenant_resolver[0] = resolver


def configure_libsql_tenant_resolver(resolver: Callable[[str], LibsqlTenant | None] | None) -> None:
    """Install (or clear) the tenant -> libSQL database resolver.

    When installed and it returns a :class:`LibsqlTenant` for a tenant, that
    tenant is served from its libSQL database via the libSQL-backed catalog
    facades. Returning None for a tenant (or passing None here) falls back to the
    filesystem resolver, so file-based tenants are unaffected.
    """
    _clear_catalog_caches()
    _libsql_resolver[0] = resolver


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
