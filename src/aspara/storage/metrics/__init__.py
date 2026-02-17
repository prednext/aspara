from aspara.config import get_storage_backend

from .base import MetricsStorage
from .jsonl import JsonlMetricsStorage
from .polars import PolarsMetricsStorage

DEFAULT_METRICS_STORAGE_BACKEND = "jsonl"
_VALID_METRICS_STORAGE_BACKENDS = {"jsonl", "polars"}


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
) -> MetricsStorage:
    """Create a metrics storage instance.

    This is the recommended way to create storage instances.
    The backend is resolved via resolve_metrics_storage_backend().

    Args:
        backend: Storage backend type ('jsonl' or 'polars').
                 If None, uses ASPARA_STORAGE_BACKEND env var or defaults to 'jsonl'.
        base_dir: Base directory for data storage.
        project_name: Name of the project.
        run_name: Name of the run.

    Returns:
        MetricsStorage instance (JsonlMetricsStorage or PolarsMetricsStorage).
    """
    resolved = resolve_metrics_storage_backend(backend)
    if resolved == "polars":
        return PolarsMetricsStorage(
            base_dir=base_dir,
            project_name=project_name,
            run_name=run_name,
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
