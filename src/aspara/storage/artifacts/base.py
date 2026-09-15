"""Artifact storage abstraction.

An artifact has two layers: its *metadata* (name, size, category, ...) and
its *bytes* (the actual file body). Metadata is handled by
``RunMetadataStorage``; this module owns the bytes.

``ArtifactStore`` is the seam that lets the byte storage backend vary
(local filesystem today, object storage or a per-run split later) without
changing the callers that write and read artifacts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class StoredArtifact:
    """A single stored artifact's identity and size."""

    name: str
    size: int


class ArtifactTooLargeError(Exception):
    """Raised when an uploaded artifact exceeds the configured size limit."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"Artifact exceeds maximum size of {limit} bytes")


class ArtifactRunNotFoundError(Exception):
    """Raised when a run has no artifact storage area at all.

    Distinct from "the run exists but has zero artifacts": callers use this
    to reproduce the historical 404 that differentiates a missing run
    directory from an empty one.
    """


class ArtifactStore(ABC):
    """Backend-agnostic storage for artifact bytes, scoped by project/run."""

    @abstractmethod
    def put_file(self, project: str, run: str, name: str, source_path: str) -> StoredArtifact:
        """Store an artifact by copying an existing local file.

        Args:
            project: Project name.
            run: Run name.
            name: Destination artifact name.
            source_path: Absolute path to the source file to store.

        Returns:
            The stored artifact's name and size.
        """

    @abstractmethod
    def put_stream(
        self,
        project: str,
        run: str,
        name: str,
        chunks: Iterable[bytes],
        *,
        max_size: int,
    ) -> StoredArtifact:
        """Store an artifact from a stream of byte chunks.

        Args:
            project: Project name.
            run: Run name.
            name: Destination artifact name.
            chunks: Iterable yielding the file body in chunks.
            max_size: Maximum allowed total size in bytes.

        Returns:
            The stored artifact's name and size.

        Raises:
            ArtifactTooLargeError: If the cumulative size exceeds ``max_size``.
        """

    @abstractmethod
    def list(self, project: str, run: str) -> Sequence[StoredArtifact]:
        """List the artifacts stored for a run.

        Args:
            project: Project name.
            run: Run name.

        Returns:
            The stored artifacts (may be empty if the run has an artifact
            area but no files).

        Raises:
            ArtifactRunNotFoundError: If no artifact storage area exists for
                the run.
        """

    @abstractmethod
    def open(self, project: str, run: str, name: str) -> BinaryIO:
        """Open a stored artifact for binary reading.

        Args:
            project: Project name.
            run: Run name.
            name: Artifact name.

        Returns:
            A binary file-like object positioned at the start.
        """

    @abstractmethod
    def delete_run(self, project: str, run: str) -> None:
        """Remove all artifact bytes stored for a run.

        Missing storage is a no-op. Names must be validated so a bad project
        or run cannot escape the store's root.
        """

    @abstractmethod
    def delete_project(self, project: str) -> None:
        """Remove all artifact bytes stored for a project (every run).

        Missing storage is a no-op. Must not delete the store's root (where a
        local libSQL tenant keeps ``aspara.db``).
        """

    @abstractmethod
    def delete_file(self, project: str, run: str, name: str) -> None:
        """Remove one stored artifact file. Missing files are a no-op."""
