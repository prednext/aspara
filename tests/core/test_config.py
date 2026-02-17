"""Tests for config module."""

from pathlib import Path

from aspara.config import get_data_dir


class TestGetDataDir:
    """Tests for get_data_dir function."""

    def test_aspara_data_dir_takes_priority(self, monkeypatch):
        """Test that ASPARA_DATA_DIR has highest priority."""
        monkeypatch.setenv("ASPARA_DATA_DIR", "/custom/aspara/data")
        monkeypatch.setenv("XDG_DATA_HOME", "/should/not/be/used")

        result = get_data_dir()

        assert result == Path("/custom/aspara/data")

    def test_xdg_data_home_used_when_aspara_data_dir_not_set(self, monkeypatch):
        """Test that XDG_DATA_HOME/aspara is used when ASPARA_DATA_DIR not set."""
        monkeypatch.delenv("ASPARA_DATA_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", "/home/user/.local/share")

        result = get_data_dir()

        assert result == Path("/home/user/.local/share/aspara")

    def test_fallback_to_home_local_share(self, monkeypatch):
        """Test fallback to ~/.local/share/aspara when no env vars set."""
        monkeypatch.delenv("ASPARA_DATA_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)

        result = get_data_dir()

        assert result == Path.home() / ".local" / "share" / "aspara"

    def test_path_expansion_with_tilde(self, monkeypatch):
        """Test that ~ is expanded in ASPARA_DATA_DIR."""
        monkeypatch.setenv("ASPARA_DATA_DIR", "~/custom/data")

        result = get_data_dir()

        assert result == Path.home() / "custom" / "data"
        assert "~" not in str(result)

    def test_xdg_path_expansion_with_tilde(self, monkeypatch):
        """Test that ~ is expanded in XDG_DATA_HOME."""
        monkeypatch.delenv("ASPARA_DATA_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", "~/custom/.local/share")

        result = get_data_dir()

        assert result == Path.home() / "custom" / ".local" / "share" / "aspara"
        assert "~" not in str(result)

    def test_returns_path_object(self, monkeypatch):
        """Test that function returns Path object."""
        monkeypatch.delenv("ASPARA_DATA_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)

        result = get_data_dir()

        assert isinstance(result, Path)

    def test_empty_aspara_data_dir_uses_xdg(self, monkeypatch):
        """Test that empty ASPARA_DATA_DIR falls through to XDG_DATA_HOME."""
        monkeypatch.setenv("ASPARA_DATA_DIR", "")
        monkeypatch.setenv("XDG_DATA_HOME", "/home/user/.local/share")

        result = get_data_dir()

        assert result == Path("/home/user/.local/share/aspara")

    def test_empty_xdg_data_home_uses_fallback(self, monkeypatch):
        """Test that empty XDG_DATA_HOME falls through to fallback."""
        monkeypatch.delenv("ASPARA_DATA_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", "")

        result = get_data_dir()

        assert result == Path.home() / ".local" / "share" / "aspara"
