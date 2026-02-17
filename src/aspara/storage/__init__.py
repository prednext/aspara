"""
Aspara Storage module

Provides MetricsStorage interface and implementations for persisting metrics data.
"""

from .metadata import ProjectMetadataStorage, RunMetadataStorage
from .metrics import (
    JsonlMetricsStorage,  # noqa: F401
    MetricsStorage,
    PolarsMetricsStorage,  # noqa: F401
    create_metrics_storage,
    resolve_metrics_storage_backend,
)

__all__ = [
    "MetricsStorage",
    "create_metrics_storage",
    "resolve_metrics_storage_backend",
    "ProjectMetadataStorage",
    "RunMetadataStorage",
]
# Note: JsonlMetricsStorage, PolarsMetricsStorage are imported but not in __all__
# Internal code can still use explicit imports
