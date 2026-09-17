"""Assemble per-tenant storage from ``aspara.tenancy``.

Dashboard (read) and tracker (write) both decide "what backs this tenant?"
through these helpers so filesystem tenants cannot fall through to a
process-wide ``ASPARA_LIBSQL_URL``, and so artifact bytes use one rule.
``aspara.tenancy`` stays location-only and does not import storage.
"""

from __future__ import annotations

from aspara.storage.artifacts import ArtifactStore, FilesystemArtifactStore
from aspara.storage.metadata.libsql import LibsqlProjectMetadataStorage, LibsqlRunMetadataStorage
from aspara.storage.metadata.project import ProjectMetadataStorage
from aspara.storage.metadata.run import RunMetadataStorage
from aspara.storage.metrics import (
    DEFAULT_METRICS_STORAGE_BACKEND,
    create_metrics_storage_with_backend,
    resolve_metrics_storage_backend,
)
from aspara.storage.metrics.base import MetricsStorage
from aspara.tenancy import resolve_artifact_base_dir, resolve_data_dir, resolve_libsql_tenant


def metrics_storage_for_tenant(tenant_id: str, project_name: str, run_name: str) -> MetricsStorage:
    """Metrics storage for a tenant: libSQL spec, or jsonl/polars on the tenant dir.

    A libSQL tenant always uses that tenant's database (never ``ASPARA_STORAGE_BACKEND``
    or ``ASPARA_LIBSQL_URL``). Filesystem tenants keep jsonl/polars; if the env
    backend is ``libsql`` they still write jsonl so they cannot share one URL.
    """
    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        return create_metrics_storage_with_backend(
            "libsql",
            base_dir=spec.base_dir or "",
            project_name=project_name,
            run_name=run_name,
            database=spec.database,
            auth_token=spec.auth_token,
            reuse_connection=True,
        )
    backend = resolve_metrics_storage_backend(None)
    if backend == "libsql":
        backend = DEFAULT_METRICS_STORAGE_BACKEND
    return create_metrics_storage_with_backend(
        backend,
        base_dir=str(resolve_data_dir(tenant_id)),
        project_name=project_name,
        run_name=run_name,
    )


def run_metadata_for_tenant(tenant_id: str, project_name: str, run_name: str) -> RunMetadataStorage:
    """Run metadata storage for a tenant (libSQL ``run_meta`` or ``*.meta.json``)."""
    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        return LibsqlRunMetadataStorage(
            spec.base_dir or "",
            project_name,
            run_name,
            database=spec.database,
            auth_token=spec.auth_token,
            reuse_connection=True,
        )
    data_dir = resolve_data_dir(tenant_id)
    return RunMetadataStorage(
        base_dir=str(data_dir),
        project_name=project_name,
        run_name=run_name,
    )


def project_metadata_for_tenant(tenant_id: str, project_name: str) -> ProjectMetadataStorage:
    """Project metadata storage for a tenant (libSQL ``project_meta`` or ``metadata.json``)."""
    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        return LibsqlProjectMetadataStorage(
            spec.base_dir or "",
            project_name,
            database=spec.database,
            auth_token=spec.auth_token,
            reuse_connection=True,
        )
    data_dir = resolve_data_dir(tenant_id)
    return ProjectMetadataStorage(base_dir=str(data_dir), project_name=project_name)


def artifact_store_for_tenant(tenant_id: str) -> ArtifactStore | None:
    """Local artifact-byte store for a tenant, or None when there is no local root.

    Remote libSQL tenants return None so callers reject upload/ZIP instead of
    writing into a shared data directory.
    """
    root = resolve_artifact_base_dir(tenant_id)
    if root is None:
        return None
    return FilesystemArtifactStore(root)
