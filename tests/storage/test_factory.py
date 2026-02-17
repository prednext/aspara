"""Tests for create_metrics_storage factory function."""

import pytest

from aspara.storage import (
    MetricsStorage,
    create_metrics_storage,
)
from aspara.storage.metrics import JsonlMetricsStorage, PolarsMetricsStorage


class TestCreateMetricsStorage:
    """Tests for the create_metrics_storage factory function."""

    def test_creates_jsonl_storage_by_default(self, tmp_path: str) -> None:
        """Default backend should be jsonl."""
        storage = create_metrics_storage(
            base_dir=str(tmp_path),
            project_name="test-project",
            run_name="test-run",
        )
        assert isinstance(storage, JsonlMetricsStorage)
        assert isinstance(storage, MetricsStorage)

    def test_creates_jsonl_storage_explicitly(self, tmp_path: str) -> None:
        """Explicit jsonl backend should create JsonlMetricsStorage."""
        storage = create_metrics_storage(
            backend="jsonl",
            base_dir=str(tmp_path),
            project_name="test-project",
            run_name="test-run",
        )
        assert isinstance(storage, JsonlMetricsStorage)

    def test_creates_polars_storage_explicitly(self, tmp_path: str) -> None:
        """Explicit polars backend should create PolarsMetricsStorage."""
        storage = create_metrics_storage(
            backend="polars",
            base_dir=str(tmp_path),
            project_name="test-project",
            run_name="test-run",
        )
        assert isinstance(storage, PolarsMetricsStorage)
        assert isinstance(storage, MetricsStorage)

    def test_env_variable_overrides_argument(self, tmp_path: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """ASPARA_STORAGE_BACKEND env var should override backend argument."""
        monkeypatch.setenv("ASPARA_STORAGE_BACKEND", "polars")
        storage = create_metrics_storage(
            backend="jsonl",
            base_dir=str(tmp_path),
            project_name="test-project",
            run_name="test-run",
        )
        assert isinstance(storage, PolarsMetricsStorage)

    def test_invalid_backend_raises_error(self, tmp_path: str) -> None:
        """Invalid backend should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid storage_backend value"):
            create_metrics_storage(
                backend="invalid",
                base_dir=str(tmp_path),
                project_name="test-project",
                run_name="test-run",
            )


class TestExplicitImports:
    """Tests that internal explicit imports still work."""

    def test_explicit_jsonl_import(self) -> None:
        """Direct import of JsonlMetricsStorage should work."""
        from aspara.storage.metrics import JsonlMetricsStorage

        assert JsonlMetricsStorage is not None

    def test_explicit_polars_import(self) -> None:
        """Direct import of PolarsMetricsStorage should work."""
        from aspara.storage.metrics import PolarsMetricsStorage

        assert PolarsMetricsStorage is not None

    def test_storage_package_import(self) -> None:
        """Imports from aspara.storage should still expose concrete classes."""
        from aspara.storage import JsonlMetricsStorage, PolarsMetricsStorage

        assert JsonlMetricsStorage is not None
        assert PolarsMetricsStorage is not None
