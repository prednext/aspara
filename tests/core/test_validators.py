"""Tests for security validators."""

from pathlib import Path

import pytest

from aspara.utils.validators import (
    validate_name,
    validate_project_name,
    validate_run_name,
    validate_safe_path,
)


def test_validate_safe_path_valid_path(tmp_path):
    """Test that valid paths within base directory pass validation."""
    base_dir = tmp_path / "data"
    base_dir.mkdir()

    # Direct subdirectory - should not raise
    valid_path = base_dir / "project"
    validate_safe_path(valid_path, base_dir)

    # Nested subdirectory - should not raise
    nested_path = base_dir / "project" / "run"
    validate_safe_path(nested_path, base_dir)

    # Base directory itself - should not raise
    validate_safe_path(base_dir, base_dir)


def test_validate_safe_path_path_traversal_attempt(tmp_path):
    """Test that path traversal attempts raise ValueError."""
    base_dir = tmp_path / "data"
    base_dir.mkdir()

    # Parent directory traversal using ..
    traversal_path = base_dir / ".." / "etc" / "passwd"
    with pytest.raises(ValueError):
        validate_safe_path(traversal_path, base_dir)

    # Multiple parent directory traversals
    deep_traversal = base_dir / "project" / ".." / ".." / "etc"
    with pytest.raises(ValueError):
        validate_safe_path(deep_traversal, base_dir)


def test_validate_safe_path_absolute_path_outside(tmp_path):
    """Test that absolute paths outside base directory raise ValueError."""
    base_dir = tmp_path / "data"
    base_dir.mkdir()

    # Different directory entirely
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    with pytest.raises(ValueError):
        validate_safe_path(other_dir, base_dir)

    # System directory
    system_path = Path("/etc/passwd")
    with pytest.raises(ValueError):
        validate_safe_path(system_path, base_dir)


def test_validate_safe_path_symlink_escape(tmp_path):
    """Test that symlinks escaping base directory raise ValueError."""
    base_dir = tmp_path / "data"
    base_dir.mkdir()

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    # Create symlink inside base_dir pointing outside
    symlink_path = base_dir / "escape"
    symlink_path.symlink_to(outside_dir)

    # Following the symlink should escape base_dir
    with pytest.raises(ValueError):
        validate_safe_path(symlink_path, base_dir)


def test_validate_safe_path_nonexistent_path(tmp_path):
    """Test handling of non-existent paths."""
    base_dir = tmp_path / "data"
    base_dir.mkdir()

    # Non-existent path within base_dir - should still validate correctly
    nonexistent_valid = base_dir / "project" / "run"
    validate_safe_path(nonexistent_valid, base_dir)  # Should not raise

    # Non-existent path with traversal attempt
    nonexistent_traversal = base_dir / ".." / "etc"
    with pytest.raises(ValueError):
        validate_safe_path(nonexistent_traversal, base_dir)


def test_validate_safe_path_edge_cases(tmp_path):
    """Test edge cases and special scenarios."""
    base_dir = tmp_path / "data"
    base_dir.mkdir()

    # Path with special characters (but still valid)
    special_path = base_dir / "project-name_123"
    validate_safe_path(special_path, base_dir)  # Should not raise

    # Empty subdirectory name (current directory reference)
    current_ref = base_dir / "."
    validate_safe_path(current_ref, base_dir)  # Should not raise


def test_validate_safe_path_invalid_input():
    """Test handling of invalid input that might raise exceptions."""
    # If path resolution fails for any reason, should raise ValueError
    base_dir = Path("/valid/path")

    # These should raise ValueError
    with pytest.raises(ValueError):
        validate_safe_path(Path("/dev/null"), base_dir)


# Tests for validate_name function


def test_validate_name_valid_names():
    """Test that valid names pass validation."""
    # Alphanumeric
    validate_name("project123", "project")
    validate_name("run456", "run")

    # With underscores
    validate_name("my_project", "project")
    validate_name("test_run_001", "run")

    # With hyphens
    validate_name("my-project", "project")
    validate_name("test-run-001", "run")

    # Mixed
    validate_name("project-name_123", "project")
    validate_name("RuN_NaMe-001", "run")


def test_validate_name_invalid_names():
    """Test that invalid names raise ValueError."""
    # Empty string
    with pytest.raises(ValueError, match="Invalid project"):
        validate_name("", "project")

    # Path traversal attempts
    with pytest.raises(ValueError, match="Invalid project"):
        validate_name("../etc/passwd", "project")

    with pytest.raises(ValueError, match="Invalid run"):
        validate_name("../../etc", "run")

    # Special characters
    with pytest.raises(ValueError, match="Invalid project"):
        validate_name("project@name", "project")

    with pytest.raises(ValueError, match="Invalid run"):
        validate_name("run name", "run")  # space

    with pytest.raises(ValueError, match="Invalid project"):
        validate_name("project/name", "project")  # slash

    with pytest.raises(ValueError, match="Invalid run"):
        validate_name("run\\name", "run")  # backslash

    with pytest.raises(ValueError, match="Invalid project"):
        validate_name("project.name", "project")  # dot

    with pytest.raises(ValueError, match="Invalid run"):
        validate_name("run$name", "run")  # dollar sign


def test_validate_name_custom_type():
    """Test that custom name types are reflected in error messages."""
    with pytest.raises(ValueError, match="Invalid custom type"):
        validate_name("invalid/name", "custom type")


# Tests for validate_project_name function


def test_validate_project_name_valid():
    """Test that valid project names pass validation."""
    validate_project_name("my_project")
    validate_project_name("project-123")
    validate_project_name("ProjectName")
    validate_project_name("test_project_001")


def test_validate_project_name_invalid():
    """Test that invalid project names raise ValueError."""
    with pytest.raises(ValueError, match="Invalid project name"):
        validate_project_name("")

    with pytest.raises(ValueError, match="Invalid project name"):
        validate_project_name("../etc")

    with pytest.raises(ValueError, match="Invalid project name"):
        validate_project_name("project name")  # space


# Tests for validate_run_name function


def test_validate_run_name_valid():
    """Test that valid run names pass validation."""
    validate_run_name("my_run")
    validate_run_name("run-123")
    validate_run_name("RunName")
    validate_run_name("test_run_001")


def test_validate_run_name_invalid():
    """Test that invalid run names raise ValueError."""
    with pytest.raises(ValueError, match="Invalid run name"):
        validate_run_name("")

    with pytest.raises(ValueError, match="Invalid run name"):
        validate_run_name("../../passwd")

    with pytest.raises(ValueError, match="Invalid run name"):
        validate_run_name("run name")  # space
