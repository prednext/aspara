"""Capture code state for a run without user-specified SHAs."""

from __future__ import annotations

import errno
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aspara.utils.validators import validate_safe_path


def _source_max_bytes() -> int:
    raw = os.environ.get("ASPARA_SOURCE_MAX_BYTES", "1000000")
    try:
        return max(0, int(raw))
    except ValueError:
        return 1_000_000


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def sanitize_remote_url(url: str) -> str:
    """Drop userinfo (tokens) from a git remote URL. Leave scp-style URLs as-is."""
    if not url or "://" not in url:
        return url
    parts = urlsplit(url)
    if not parts.username and not parts.password:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _find_git_root(start: Path) -> Path | None:
    proc = _git("rev-parse", "--show-toplevel", cwd=start)
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return Path(root) if root else None


def _write_bytes_nofollow(path: Path, payload: bytes) -> None:
    """Create or replace ``path`` without following a symlink at the final component."""
    if path.is_symlink():
        raise ValueError(f"Refusing to follow symlink: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o666)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError(f"Refusing to follow symlink: {path}") from exc
        raise
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)


def capture_code_state(
    cwd: Path | None = None,
    *,
    dest_dir: Path | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Record git HEAD and, if dirty, a diff. Never runs ``git commit``.

    Init must succeed even when git is missing or the tree is too large.
    A diff is written only when ``dest_dir / code.diff`` stays inside ``base_dir``.
    """
    start = Path(cwd or os.getcwd())
    max_bytes = _source_max_bytes()
    try:
        root = _find_git_root(start)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"kind": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

    if root is None:
        return {"kind": "unavailable", "error": "not a git repository"}

    head = _git("rev-parse", "HEAD", cwd=root)
    if head.returncode != 0:
        return {"kind": "unavailable", "error": head.stderr.strip() or "git rev-parse HEAD failed"}

    sha = head.stdout.strip()
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).stdout.strip()
    remote = _git("remote", "get-url", "origin", cwd=root)
    remote_url = sanitize_remote_url(remote.stdout.strip()) if remote.returncode == 0 else ""
    porcelain = _git("status", "--porcelain", cwd=root)
    dirty = bool(porcelain.stdout.strip())

    code: dict[str, Any] = {
        "kind": "git",
        "sha": sha,
        "dirty": dirty,
        "branch": branch,
        "remote": remote_url,
    }

    if not dirty:
        return code

    diff = _git("diff", "HEAD", cwd=root)
    payload = diff.stdout.encode("utf-8")
    if not payload:
        code["snapshot_skipped"] = "empty_diff"
        return code
    if len(payload) > max_bytes:
        code["snapshot_skipped"] = "over_max_bytes"
        code["diff_bytes"] = len(payload)
        return code
    if dest_dir is None:
        code["snapshot_skipped"] = "no_dest"
        return code
    if base_dir is None:
        code["snapshot_skipped"] = "unsafe_path"
        return code
    dest = dest_dir / "code.diff"
    try:
        validate_safe_path(dest, base_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        validate_safe_path(dest, base_dir)
        _write_bytes_nofollow(dest, payload)
    except ValueError:
        code["snapshot_skipped"] = "unsafe_path"
        return code
    code["snapshot_relpath"] = "source/code.diff"
    return code
