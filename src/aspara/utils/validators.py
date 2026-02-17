"""Security validators for Aspara.

This module provides common validation functions to prevent security vulnerabilities
like path traversal attacks.
"""

import os
import re
from pathlib import Path

__all__ = ["validate_safe_path", "validate_name", "validate_project_name", "validate_run_name", "validate_artifact_name"]

# Security validation pattern for project/run names
# Only allow alphanumeric characters, underscores, and hyphens
_SAFE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# More permissive pattern for artifact/file names
# Allows alphanumeric, underscores, hyphens, and dots (for file extensions)
# Does NOT allow: slashes, backslashes, null bytes, or special path components
_SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.\-]+$")


def validate_safe_path(path: Path, base_dir: Path) -> None:
    """Validate that the resolved path is within the base directory.

    This function prevents path traversal attacks by ensuring that the resolved
    absolute path stays within the base directory boundaries. It also checks for
    symlinks in the path to prevent symlink-based attacks.

    Args:
        path: Path to validate
        base_dir: Base directory that should contain the path

    Raises:
        ValueError: If path is outside base_dir, contains symlinks, or path resolution fails

    Examples:
        >>> base = Path("/data")
        >>> validate_safe_path(Path("/data/project/run"), base)  # OK
        >>> validate_safe_path(Path("/data/../etc/passwd"), base)  # Raises ValueError
    """
    try:
        # First resolve both paths to absolute paths
        resolved_path = path.resolve()
        resolved_base = base_dir.resolve()

        # Check for symlinks in the path hierarchy
        # Walk from the path up to the base directory, checking each component
        current = path
        while current != current.parent:
            if current.exists() and current.is_symlink():
                raise ValueError(f"Path contains symlink: {current}")
            # Stop checking when we reach the base directory
            try:
                current.relative_to(resolved_base)
            except ValueError:
                # We've gone above the base directory, stop checking
                break
            current = current.parent

        # Check if the resolved path is within the base directory
        # Use os.path.commonpath for more robust comparison
        if not str(resolved_path).startswith(str(resolved_base) + os.sep) and resolved_path != resolved_base:
            raise ValueError(f"Path {path} is outside base directory {base_dir}")
    except (ValueError, OSError) as e:
        # If path resolution fails or validation fails, raise error
        if isinstance(e, ValueError) and str(e).startswith("Path"):
            raise
        raise ValueError(f"Invalid path: {path}") from e


def validate_name(name: str, name_type: str = "name") -> None:
    """Validate a name to prevent path traversal attacks.

    This function ensures that names (project names, run names, etc.) only contain
    safe characters to prevent directory traversal and other security vulnerabilities.

    Args:
        name: Name from user input
        name_type: Type of name (for error messages), e.g., "project", "run"

    Raises:
        ValueError: If name is empty or contains invalid characters

    Examples:
        >>> validate_name("my_project", "project")  # OK
        >>> validate_name("../etc/passwd", "project")  # Raises ValueError
        >>> validate_name("", "project")  # Raises ValueError
    """
    if not name or not _SAFE_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid {name_type}. Only alphanumeric characters, underscores, and hyphens are allowed.")


def validate_project_name(project: str) -> None:
    """Validate project name to prevent path traversal attacks.

    Args:
        project: Project name from user input

    Raises:
        ValueError: If project name contains invalid characters

    Examples:
        >>> validate_project_name("my_project")  # OK
        >>> validate_project_name("../etc")  # Raises ValueError
    """
    validate_name(project, "project name")


def validate_run_name(run: str) -> None:
    """Validate run name to prevent path traversal attacks.

    Args:
        run: Run name from user input

    Raises:
        ValueError: If run name contains invalid characters

    Examples:
        >>> validate_run_name("experiment_001")  # OK
        >>> validate_run_name("../../passwd")  # Raises ValueError
    """
    validate_name(run, "run name")


def validate_artifact_name(name: str) -> None:
    """Validate an artifact/file name.

    Artifact names can contain alphanumeric characters, underscores, hyphens, and dots
    (for file extensions). This is more permissive than project/run names but still
    prevents path traversal attacks.

    Args:
        name: Artifact name to validate

    Raises:
        ValueError: If name is invalid or could enable path traversal

    Examples:
        >>> validate_artifact_name("model.pt")  # OK
        >>> validate_artifact_name("test_file.txt")  # OK
        >>> validate_artifact_name("../etc/passwd")  # Raises ValueError
        >>> validate_artifact_name("..hidden")  # Raises ValueError (starts with ..)
    """
    if not name:
        raise ValueError("Invalid artifact name: cannot be empty")

    if len(name) > 255:
        raise ValueError("Invalid artifact name: exceeds maximum length of 255 characters")

    # Block path traversal attempts
    if name in (".", ".."):
        raise ValueError(f"Invalid artifact name: cannot be '{name}'")

    # Block names starting with ".." (potential path traversal)
    if name.startswith(".."):
        raise ValueError("Invalid artifact name: cannot start with '..'")

    # Validate characters
    if not _SAFE_FILENAME_PATTERN.match(name):
        raise ValueError(f"Invalid artifact name: '{name}'. Names can only contain alphanumeric characters, underscores, hyphens, and dots.")
