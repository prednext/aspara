"""
FastAPI dependency injection for Aspara Dashboard.

This module provides reusable dependencies for:
- Catalog instance management (ProjectCatalog, RunCatalog)
- Path parameter validation (project names, run names)
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi import Path as PathParam

from aspara.catalog import LibsqlCatalog, ProjectCatalog, RunCatalog
from aspara.catalog.libsql_adapters import LibsqlProjectCatalog, LibsqlRunCatalog
from aspara.storage.artifacts import ArtifactStore
from aspara.storage.tenant import artifact_store_for_tenant
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
    "ArtifactStoreDep",
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


class _LibsqlCatalogEntry:
    """Cached libSQL catalogs plus a borrow count so eviction cannot close in-use connections."""

    __slots__ = ("project_cat", "run_cat", "data_dir", "refs")

    def __init__(
        self,
        project_cat: LibsqlProjectCatalog,
        run_cat: LibsqlRunCatalog,
        data_dir: Path,
    ) -> None:
        self.project_cat = project_cat
        self.run_cat = run_cat
        self.data_dir = data_dir
        self.refs = 0


_libsql_catalog_lock = threading.Lock()
_libsql_catalog_cache: OrderedDict[
    tuple[str | None, str | None, str | None],
    _LibsqlCatalogEntry,
] = OrderedDict()
_LIBSQL_CATALOG_CACHE_MAX = 32


def _borrow_libsql_catalogs(
    base_dir: str | None,
    database: str | None,
    auth_token: str | None,
    artifact_store: ArtifactStore | None,
) -> tuple[tuple[LibsqlProjectCatalog, LibsqlRunCatalog, Path], Callable[[], None]]:
    """Borrow cached libSQL catalogs for one tenant database.

    Concurrent first access shares one connection. Eviction closes only idle
    entries (``refs == 0``). The caller must invoke the returned release
    function exactly once.
    """
    key = (base_dir, database, auth_token)
    with _libsql_catalog_lock:
        entry = _libsql_catalog_cache.get(key)
        if entry is None:
            while len(_libsql_catalog_cache) >= _LIBSQL_CATALOG_CACHE_MAX:
                victim_key = next((k for k, v in _libsql_catalog_cache.items() if v.refs == 0), None)
                if victim_key is None:
                    break
                victim = _libsql_catalog_cache.pop(victim_key)
                victim.project_cat.close()
            catalog = LibsqlCatalog(base_dir=base_dir, database=database, auth_token=auth_token)
            lock = threading.RLock()
            data_dir = Path(base_dir) if base_dir else Path(".")
            entry = _LibsqlCatalogEntry(
                LibsqlProjectCatalog(catalog, lock, artifact_store),
                LibsqlRunCatalog(catalog, lock, artifact_store),
                data_dir,
            )
            _libsql_catalog_cache[key] = entry
        else:
            _libsql_catalog_cache.move_to_end(key)
        entry.refs += 1
        catalogs = (entry.project_cat, entry.run_cat, entry.data_dir)

    released = False

    def release() -> None:
        nonlocal released
        if released:
            return
        released = True
        with _libsql_catalog_lock:
            current = _libsql_catalog_cache.get(key)
            if current is not None:
                current.refs = max(0, current.refs - 1)

    return catalogs, release


def _tenant_id_from_request(request: Request | None) -> str:
    """Read the tenant id set on the request state, defaulting to DEFAULT_TENANT."""
    if request is not None:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return str(tenant_id)
    return DEFAULT_TENANT


def _borrow_catalogs_for_request(
    request: Request | None,
) -> tuple[tuple[ProjectCatalogLike, RunCatalogLike, Path], Callable[[], None]]:
    """Resolve catalogs for the request's tenant and a matching release callback."""
    tenant_id = _tenant_id_from_request(request)

    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        return _borrow_libsql_catalogs(
            spec.base_dir,
            spec.database,
            spec.auth_token,
            artifact_store_for_tenant(tenant_id),
        )

    data_dir = resolve_data_dir(tenant_id)
    return _catalogs_for_dir(str(data_dir)), lambda: None


def _get_catalogs() -> tuple[ProjectCatalog, RunCatalog, Path]:
    """Backward-compatible accessor for the default tenant's (filesystem) catalogs."""
    return _catalogs_for_dir(str(resolve_data_dir(DEFAULT_TENANT)))


def get_project_catalog(request: Request) -> Iterator[ProjectCatalogLike]:
    """Get the project catalog for the request's tenant."""
    catalogs, release = _borrow_catalogs_for_request(request)
    try:
        yield catalogs[0]
    finally:
        release()


def get_run_catalog(request: Request) -> Iterator[RunCatalogLike]:
    """Get the run catalog for the request's tenant."""
    catalogs, release = _borrow_catalogs_for_request(request)
    try:
        yield catalogs[1]
    finally:
        release()


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


def get_artifact_store(request: Request) -> ArtifactStore:
    """Get the artifact-byte store for the request's tenant.

    Remote libSQL tenants have no local bytes, so this raises 404.
    """
    store = artifact_store_for_tenant(_tenant_id_from_request(request))
    if store is None:
        raise HTTPException(status_code=404, detail="No artifacts found for this run")
    return store


def _clear_catalog_caches() -> None:
    """Drop all cached catalog instances (file-based and libSQL-backed)."""
    _catalogs_for_dir.cache_clear()
    with _libsql_catalog_lock:
        entries = list(_libsql_catalog_cache.values())
        _libsql_catalog_cache.clear()
    for entry in entries:
        entry.project_cat.close()


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
ArtifactStoreDep = Annotated[ArtifactStore, Depends(get_artifact_store)]
