"""Tests for the TUI application."""

from __future__ import annotations

from pathlib import Path

from aspara.tui.app import AsparaTUIApp


class TestAsparaTUIApp:
    """Tests for AsparaTUIApp class."""

    def test_app_initialization_with_default_data_dir(self) -> None:
        """Test that app initializes with default data directory."""
        app = AsparaTUIApp()
        assert app.data_dir is not None
        assert isinstance(app.data_dir, Path)

    def test_app_initialization_with_custom_data_dir(self, tmp_path: Path) -> None:
        """Test that app initializes with custom data directory."""
        app = AsparaTUIApp(data_dir=str(tmp_path))
        assert app.data_dir == tmp_path

    def test_app_has_required_bindings(self) -> None:
        """Test that app has required key bindings."""
        app = AsparaTUIApp()
        binding_keys = [b.key for b in app.BINDINGS]
        assert "q" in binding_keys
        assert "question_mark" in binding_keys
        assert "escape" in binding_keys

    def test_project_catalog_lazy_initialization(self, tmp_path: Path) -> None:
        """Test that project catalog is lazily initialized."""
        app = AsparaTUIApp(data_dir=str(tmp_path))
        assert app._project_catalog is None
        _ = app.project_catalog
        assert app._project_catalog is not None

    def test_run_catalog_lazy_initialization(self, tmp_path: Path) -> None:
        """Test that run catalog is lazily initialized."""
        app = AsparaTUIApp(data_dir=str(tmp_path))
        assert app._run_catalog is None
        _ = app.run_catalog
        assert app._run_catalog is not None
