from aspara.config import get_libsql_auth_token, get_libsql_url, get_storage_backend

from .base import MetricsStorage
from .jsonl import JsonlMetricsStorage
from .polars import PolarsMetricsStorage

DEFAULT_METRICS_STORAGE_BACKEND = "jsonl"
# "libsql" is an optional backend (multi-tenant SaaS path); its module and the
# ``libsql`` package are imported lazily in create_metrics_storage() so the
# dependency is only required when the backend is actually selected.
_VALID_METRICS_STORAGE_BACKENDS = {"jsonl", "polars", "libsql"}


def resolve_metrics_storage_backend(storage_backend: str | None = None) -> str:
    """Resolve the metrics storage backend name.

    Resolution order:
    1. ASPARA_STORAGE_BACKEND environment variable (if set and valid)
    2. storage_backend argument (if set and valid)
    3. DEFAULT_METRICS_STORAGE_BACKEND ("jsonl") when neither is set

    Raises:
        ValueError: If ASPARA_STORAGE_BACKEND or storage_backend is set but invalid.
    """

    env_backend = get_storage_backend()

    if env_backend is not None:
        if env_backend in _VALID_METRICS_STORAGE_BACKENDS:
            return env_backend
        msg = f"Invalid ASPARA_STORAGE_BACKEND value: {env_backend!r}. Valid values are: {sorted(_VALID_METRICS_STORAGE_BACKENDS)}"
        raise ValueError(msg)

    if storage_backend is not None:
        if storage_backend in _VALID_METRICS_STORAGE_BACKENDS:
            return storage_backend
        msg = f"Invalid storage_backend value: {storage_backend!r}. Valid values are: {sorted(_VALID_METRICS_STORAGE_BACKENDS)}"
        raise ValueError(msg)

    return DEFAULT_METRICS_STORAGE_BACKEND


def create_metrics_storage(
    backend: str | None = None,
    *,
    base_dir: str,
    project_name: str,
    run_name: str,
    database: str | None = None,
    auth_token: str | None = None,
) -> MetricsStorage:
    """Create a metrics storage instance.

    This is the recommended way to create storage instances.
    The backend is resolved via resolve_metrics_storage_backend().

    Args:
        backend: Storage backend type ('jsonl', 'polars', or 'libsql').
                 If None, uses ASPARA_STORAGE_BACKEND env var or defaults to 'jsonl'.
                 'libsql' targets a local database file, or a remote Turso database
                 when ASPARA_LIBSQL_URL / ASPARA_LIBSQL_AUTH_TOKEN are set.
        base_dir: Base directory for data storage.
        project_name: Name of the project.
        run_name: Name of the run.
        database: Explicit libSQL database URL for a per-tenant remote connection.
                  When None, falls back to the ASPARA_LIBSQL_URL env var. Only used
                  by the 'libsql' backend.
        auth_token: Explicit auth token for a per-tenant remote database. When None,
                    falls back to the ASPARA_LIBSQL_AUTH_TOKEN env var. Only used by
                    the 'libsql' backend.

    Returns:
        MetricsStorage instance (Jsonl/Polars/Libsql MetricsStorage).
    """
    resolved = resolve_metrics_storage_backend(backend)
    if resolved == "polars":
        return PolarsMetricsStorage(
            base_dir=base_dir,
            project_name=project_name,
            run_name=run_name,
        )
    if resolved == "libsql":
        # Lazy import so the optional ``libsql`` dependency is only required here.
        from .libsql import LibsqlMetricsStorage

        return LibsqlMetricsStorage(
            base_dir=base_dir,
            project_name=project_name,
            run_name=run_name,
            database=database if database is not None else get_libsql_url(),
            auth_token=auth_token if auth_token is not None else get_libsql_auth_token(),
        )
    return JsonlMetricsStorage(
        base_dir=base_dir,
        project_name=project_name,
        run_name=run_name,
    )


__all__ = [
    "MetricsStorage",
    "JsonlMetricsStorage",
    "PolarsMetricsStorage",
    "create_metrics_storage",
    "resolve_metrics_storage_backend",
]
