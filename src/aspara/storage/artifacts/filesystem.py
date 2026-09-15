"""Filesystem-backed artifact store.

Preserves the historical on-disk layout so behaviour is unchanged:

    {base_dir}/{project}/{run}/artifacts/{name}
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import BinaryIO

from aspara.utils import validators

from .base import (
    ArtifactRunNotFoundError,
    ArtifactStore,
    ArtifactTooLargeError,
    StoredArtifact,
)

logger = logging.getLogger(__name__)


class FilesystemArtifactStore(ArtifactStore):
    """Store artifact bytes as files under a base data directory."""

    def __init__(self, base_dir: str | Path) -> None:
        """Initialize the store.

        Args:
            base_dir: Top-level data directory that contains project folders.
        """
        self._base_dir = Path(base_dir)

    def _artifacts_dir(self, project: str, run: str) -> Path:
        return self._base_dir / project / run / "artifacts"

    def put_file(self, project: str, run: str, name: str, source_path: str) -> StoredArtifact:
        artifacts_dir = self._artifacts_dir(project, run)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        dest = artifacts_dir / name
        validators.validate_safe_path(dest, artifacts_dir)

        source_size = os.path.getsize(source_path)
        try:
            shutil.copy2(source_path, dest)
        except OSError as e:
            raise OSError(f"Failed to copy artifact file: {e}") from e

        # Verify the copy succeeded by comparing sizes. A partial copy
        # (e.g. disk full mid-write) would otherwise pass silently.
        dest_size = os.path.getsize(dest)
        if dest_size != source_size:
            with contextlib.suppress(OSError):
                os.remove(dest)
            raise OSError(f"Artifact copy verification failed: size mismatch (source={source_size}, dest={dest_size})")

        return StoredArtifact(name=name, size=dest_size)

    def put_stream(
        self,
        project: str,
        run: str,
        name: str,
        chunks: Iterable[bytes],
        *,
        max_size: int,
    ) -> StoredArtifact:
        artifacts_dir = self._artifacts_dir(project, run)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        dest = artifacts_dir / name
        validators.validate_safe_path(dest, artifacts_dir)
        partial = dest.with_name(dest.name + ".partial")
        validators.validate_safe_path(partial, artifacts_dir)

        written = 0
        try:
            with open(partial, "wb") as f:
                for chunk in chunks:
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_size:
                        raise ArtifactTooLargeError(max_size)
                    f.write(chunk)
            os.replace(partial, dest)
        except ArtifactTooLargeError:
            partial.unlink(missing_ok=True)
            raise
        except Exception:
            partial.unlink(missing_ok=True)
            raise

        return StoredArtifact(name=name, size=written)

    def list(self, project: str, run: str) -> Sequence[StoredArtifact]:
        artifacts_dir = self._artifacts_dir(project, run)
        validators.validate_safe_path(artifacts_dir, self._base_dir)

        if not artifacts_dir.exists():
            raise ArtifactRunNotFoundError(f"No artifacts directory for run '{run}' in project '{project}'")

        entries: list[StoredArtifact] = []
        # follow_symlinks=False prevents a local attacker from tricking the
        # ZIP builder into bundling files outside the artifacts directory.
        with os.scandir(artifacts_dir) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    # put_stream writes to ``{name}.partial`` then replaces;
                    # leftover temps must not appear in ZIP listings.
                    if entry.name.endswith(".partial"):
                        continue
                    size = entry.stat(follow_symlinks=False).st_size
                    entries.append(StoredArtifact(name=entry.name, size=size))
                elif entry.is_symlink():
                    logger.warning(f"Skipping symlink in artifacts directory: {entry.path}")
        return entries

    def open(self, project: str, run: str, name: str) -> BinaryIO:
        artifacts_dir = self._artifacts_dir(project, run)
        path = artifacts_dir / name
        validators.validate_safe_path(path, artifacts_dir)
        return open(path, "rb")

    def delete_run(self, project: str, run: str) -> None:
        validators.validate_name(project, "project name")
        validators.validate_name(run, "run name")
        run_dir = self._base_dir / project / run
        validators.validate_safe_path(run_dir, self._base_dir)
        if run_dir.exists():
            shutil.rmtree(run_dir)

    def delete_project(self, project: str) -> None:
        validators.validate_name(project, "project name")
        project_dir = self._base_dir / project
        validators.validate_safe_path(project_dir, self._base_dir)
        if project_dir.exists():
            shutil.rmtree(project_dir)

    def delete_file(self, project: str, run: str, name: str) -> None:
        validators.validate_name(project, "project name")
        validators.validate_name(run, "run name")
        validators.validate_artifact_name(name)
        path = self._artifacts_dir(project, run) / name
        validators.validate_safe_path(path, self._base_dir)
        path.unlink(missing_ok=True)
