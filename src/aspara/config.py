"""Configuration and environment handling for Aspara."""

import os
from pathlib import Path

from pydantic import BaseModel, Field

__all__ = [
    "ResourceLimits",
    "get_data_dir",
    "get_resource_limits",
    "get_storage_backend",
    "get_project_search_mode",
    "is_dev_mode",
    "is_read_only",
]


class ResourceLimits(BaseModel):
    """Resource limits configuration.

    Includes security-related limits (file size, JSONL lines) and
    performance/resource constraints (metric names, note length, tags count).

    All limits can be customized via environment variables.
    Defaults are set for internal use with generous limits.
    """

    max_file_size: int = Field(
        default=1024 * 1024 * 1024,  # 1024MB (1GB)
        description="Maximum file size in bytes",
    )

    max_jsonl_lines: int = Field(
        default=1_000_000,  # 1M lines
        description="Maximum number of lines when reading JSONL files",
    )

    max_zip_size: int = Field(
        default=1024 * 1024 * 1024,  # 1GB
        description="Maximum ZIP file size in bytes",
    )

    max_metric_names: int = Field(
        default=100,
        description="Maximum number of metric names in comma-separated list",
    )

    max_notes_length: int = Field(
        default=10 * 1024,  # 10KB
        description="Maximum notes text length in characters",
    )

    max_tags_count: int = Field(
        default=100,
        description="Maximum number of tags",
    )

    lttb_threshold: int = Field(
        default=1_000,
        description="Downsample metrics using LTTB algorithm when metric series length exceeds this threshold",
    )

    @classmethod
    def from_env(cls) -> "ResourceLimits":
        """Create ResourceLimits from environment variables.

        Environment variables:
        - ASPARA_MAX_FILE_SIZE: Maximum file size in bytes (default: 1GB)
        - ASPARA_MAX_JSONL_LINES: Maximum JSONL lines (default: 1M)
        - ASPARA_MAX_ZIP_SIZE: Maximum ZIP size in bytes (default: 1GB)
        - ASPARA_MAX_METRIC_NAMES: Maximum metric names (default: 100)
        - ASPARA_MAX_NOTES_LENGTH: Maximum notes length (default: 10KB)
        - ASPARA_MAX_TAGS_COUNT: Maximum tags count (default: 100)
        - ASPARA_LTTB_THRESHOLD: Threshold for LTTB downsampling (default: 1000)
        """
        return cls(
            max_file_size=int(os.environ.get("ASPARA_MAX_FILE_SIZE", cls.model_fields["max_file_size"].default)),
            max_jsonl_lines=int(os.environ.get("ASPARA_MAX_JSONL_LINES", cls.model_fields["max_jsonl_lines"].default)),
            max_zip_size=int(os.environ.get("ASPARA_MAX_ZIP_SIZE", cls.model_fields["max_zip_size"].default)),
            max_metric_names=int(os.environ.get("ASPARA_MAX_METRIC_NAMES", cls.model_fields["max_metric_names"].default)),
            max_notes_length=int(os.environ.get("ASPARA_MAX_NOTES_LENGTH", cls.model_fields["max_notes_length"].default)),
            max_tags_count=int(os.environ.get("ASPARA_MAX_TAGS_COUNT", cls.model_fields["max_tags_count"].default)),
            lttb_threshold=int(os.environ.get("ASPARA_LTTB_THRESHOLD", cls.model_fields["lttb_threshold"].default)),
        )


# Global resource limits instance
_resource_limits: ResourceLimits | None = None


def get_resource_limits() -> ResourceLimits:
    """Get resource limits configuration.

    Returns cached instance if already initialized.
    """
    global _resource_limits
    if _resource_limits is None:
        _resource_limits = ResourceLimits.from_env()
    return _resource_limits


# Forbidden system directories that cannot be used as data directories
_FORBIDDEN_PATHS = frozenset(["/", "/etc", "/sys", "/dev", "/bin", "/sbin", "/usr", "/var", "/boot", "/proc"])


def _validate_data_dir(data_path: Path) -> None:
    """Validate that data directory is not a dangerous system path.

    Args:
        data_path: Path to validate

    Raises:
        ValueError: If path is a forbidden system directory
    """
    resolved = data_path.resolve()
    resolved_str = str(resolved)

    for forbidden in _FORBIDDEN_PATHS:
        if resolved_str == forbidden or resolved_str.rstrip("/") == forbidden:
            raise ValueError(f"ASPARA_DATA_DIR cannot be set to system directory: {forbidden}")


def get_data_dir() -> Path:
    """Get the default data directory for Aspara.

    Resolution priority:
    1. ASPARA_DATA_DIR environment variable (if set)
    2. XDG_DATA_HOME/aspara (if XDG_DATA_HOME is set)
    3. ~/.local/share/aspara (fallback)

    Returns:
        Path object pointing to the data directory.

    Raises:
        ValueError: If ASPARA_DATA_DIR points to a system directory

    Examples:
        >>> # Using ASPARA_DATA_DIR
        >>> os.environ["ASPARA_DATA_DIR"] = "/custom/path"
        >>> get_data_dir()
        Path('/custom/path')

        >>> # Using XDG_DATA_HOME
        >>> os.environ["XDG_DATA_HOME"] = "/home/user/.local/share"
        >>> get_data_dir()
        Path('/home/user/.local/share/aspara')

        >>> # Using fallback
        >>> get_data_dir()
        Path('/home/user/.local/share/aspara')
    """
    # Priority 1: ASPARA_DATA_DIR environment variable
    aspara_data_dir = os.environ.get("ASPARA_DATA_DIR")
    if aspara_data_dir:
        data_path = Path(aspara_data_dir).expanduser().resolve()
        _validate_data_dir(data_path)
        return data_path

    # Priority 2: XDG_DATA_HOME/aspara
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "aspara"

    # Priority 3: ~/.local/share/aspara (fallback)
    return Path.home() / ".local" / "share" / "aspara"


def get_project_search_mode() -> str:
    """Get project search mode from environment variable.

    Returns:
        Project search mode ("realtime" or "manual"). Defaults to "realtime".
    """
    mode = os.environ.get("ASPARA_PROJECT_SEARCH_MODE", "realtime")
    if mode not in ("realtime", "manual"):
        return "realtime"
    return mode


def get_storage_backend() -> str | None:
    """Get storage backend from environment variable.

    Returns:
        Storage backend name if ASPARA_STORAGE_BACKEND is set, None otherwise.
    """
    return os.environ.get("ASPARA_STORAGE_BACKEND")


def use_lttb_fast() -> bool:
    """Check if fast LTTB implementation should be used.

    Returns:
        True if ASPARA_LTTB_FAST is set to "1", False otherwise.
    """
    return os.environ.get("ASPARA_LTTB_FAST") == "1"


def is_dev_mode() -> bool:
    """Check if running in development mode.

    Returns:
        True if ASPARA_DEV_MODE is set to "1", False otherwise.
    """
    return os.environ.get("ASPARA_DEV_MODE") == "1"


def is_read_only() -> bool:
    """Check if running in read-only mode.

    Returns:
        True if ASPARA_READ_ONLY is set to "1", False otherwise.
    """
    return os.environ.get("ASPARA_READ_ONLY") == "1"
