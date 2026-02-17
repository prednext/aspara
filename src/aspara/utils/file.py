"""File operation utilities for aspara."""

import contextlib
import json
import os
import platform
import stat
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import IO, Any


def datasync(fd: int) -> None:
    """Sync file data to disk.

    Uses fdatasync on Linux, fsync on macOS/other platforms.

    Args:
        fd: File descriptor to sync
    """
    if hasattr(os, "fdatasync") and platform.system() != "Darwin":
        os.fdatasync(fd)
    else:
        os.fsync(fd)


@contextlib.contextmanager
def secure_open_append(path: str | Path) -> Generator[IO[str], None, None]:
    """Securely open a file for appending with restricted permissions.

    Creates the file with 0o600 permissions if it doesn't exist.
    Uses os.open() with O_CREAT to atomically create with correct permissions.

    Args:
        path: File path to open

    Yields:
        File object opened for appending

    Examples:
        with secure_open_append("/path/to/file.txt") as f:
            f.write("data\\n")
    """
    file_path = Path(path)

    # Create parent directory if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Open with O_CREAT to create with correct permissions atomically
    # Mode 0o600 = read/write for owner only
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    fd = os.open(str(file_path), flags, 0o600)

    fd_to_close: int | None = fd
    try:
        # Convert fd to a file object
        with os.fdopen(fd, "a") as f:
            fd_to_close = None  # fd is now owned by the file object
            yield f
    finally:
        # Close fd if fdopen failed
        if fd_to_close is not None:
            os.close(fd_to_close)


def atomic_write_json(path: str | Path, data: dict[str, Any]) -> None:
    """Atomically write JSON data to a file.

    Writes to a secure temporary file first, then renames to avoid partial writes.
    Uses tempfile.NamedTemporaryFile to prevent symlink attacks and race conditions.

    Args:
        path: Target file path
        data: Dictionary to write as JSON
    """
    target_path = Path(path)
    target_dir = target_path.parent

    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)

    # Use tempfile.NamedTemporaryFile for secure temp file creation
    # - Creates file with O_EXCL flag (prevents symlink attacks)
    # - Creates in same directory as target (allows atomic rename)
    # - delete=False because we want to rename it, not delete it
    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(
            suffix=".json",
            prefix=".tmp_",
            dir=str(target_dir),
        )
        tmp_path = Path(tmp_name)

        # Write data to temp file
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            tmp_fd = None  # fd is now owned by the file object
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            datasync(f.fileno())

        # Set appropriate permissions (readable by owner only)
        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)

        # Atomically replace target file
        os.replace(tmp_path, target_path)
        tmp_path = None  # Successfully renamed, don't clean up

    finally:
        # Clean up temp file if rename failed
        if tmp_fd is not None:
            os.close(tmp_fd)
        if tmp_path is not None and tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
