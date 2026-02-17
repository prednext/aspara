"""
MetricsStorage - Abstract base class for metrics persistence.

This module defines the interface for storing and loading metrics data.
Unlike the old StorageBackend, this class focuses solely on metrics data
and does not handle project/run discovery (that's Catalog's responsibility).
"""

from abc import ABC, abstractmethod
from typing import Any

import polars as pl


class MetricsStorage(ABC):
    """Abstract base class for metrics storage.

    This class defines the interface for persisting metrics data.
    Each instance is bound to a specific project/run combination.

    Note: Project and run discovery is handled by ProjectCatalog and RunCatalog,
    not by this class.
    """

    @abstractmethod
    def save(self, metrics_data: dict[str, Any]) -> str:  # pragma: no cover - interface only
        """Save metrics data for this run.

        Args:
            metrics_data: Metrics data to save (should include timestamp, step, metrics dict)

        Returns:
            str: Request ID if available, empty string otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        metric_names: list[str] | None = None,
    ) -> pl.DataFrame:  # pragma: no cover - interface only
        """Load metrics data for this run.

        Args:
            metric_names: Optional list of metric names to filter by.
                         If None, returns all metrics.

        Returns:
            List of metrics data dictionaries, sorted by timestamp.
            Each dict contains: timestamp, step, metrics (dict of name->value)

        Raises:
            RunNotFoundError: If the run does not exist
        """
        raise NotImplementedError

    def finish(self) -> None:  # noqa: B027
        """Run completion processing (e.g., final archiving, statistics).

        Called when aspara.finish() is invoked to perform any final processing
        before the run is considered complete.

        Default implementation does nothing. Override if needed.
        """

    def close(self) -> None:  # noqa: B027
        """Close the storage backend and release any resources.

        Default implementation does nothing. Override if cleanup is needed.
        """
