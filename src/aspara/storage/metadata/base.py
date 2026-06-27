"""Base class for file-based metadata storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aspara.logger import logger
from aspara.utils import atomic_write_json

from .models import validate_metadata


class BaseMetadataStorage:
    """Base class for file-based metadata storage.

    Subclasses must set ``base_dir``, ``_metadata_path`` and ``_metadata``
    before calling :meth:`_load`, and implement :meth:`_get_metadata_path`.
    """

    base_dir: Path
    _metadata_path: Path
    _metadata: dict[str, Any]

    def _get_metadata_path(self) -> Path:
        """Return the path to the metadata file.

        Raises:
            NotImplementedError: If the subclass does not override this.
        """
        raise NotImplementedError

    def _merge_loaded(self, loaded: dict[str, Any]) -> dict[str, Any]:
        """Merge loaded JSON with defaults.

        Override in subclasses that need to normalise or fill in missing
        fields. The default implementation returns the loaded dict as-is.
        """
        return loaded

    def _load(self) -> None:
        """Load existing metadata from file if it exists.

        Uses try/except instead of an exists() check to avoid TOCTOU races.
        On ``FileNotFoundError`` the default values are kept silently; on
        corruption or read errors a warning is logged and defaults are kept.
        """
        try:
            with open(self._metadata_path, encoding="utf-8") as f:
                loaded = json.load(f)
            self._metadata = self._merge_loaded(loaded)
        except FileNotFoundError:
            # File doesn't exist yet, keep default values
            pass
        except (json.JSONDecodeError, OSError) as e:
            # File is corrupted or unreadable, keep default values
            logger.warning(f"Failed to load metadata from {self._metadata_path}: {type(e).__name__}: {e}")

    def _save(self) -> None:
        """Save metadata to file.

        Raises:
            ValueError: If the metadata file cannot be written.
        """
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            atomic_write_json(self._metadata_path, self._metadata)
        except OSError as e:
            raise ValueError(f"Failed to write metadata file: {e}") from e

    def _validate_metadata_values(self, metadata: dict[str, Any]) -> None:
        """Validate notes/tags against resource limits.

        Raises:
            ValueError: If validation fails.
        """
        validate_metadata(metadata)

    def get_metadata(self) -> dict[str, Any]:
        """Return a shallow copy of all metadata."""
        return dict(self._metadata)

    def close(self) -> None:
        """Close storage (no-op for file-based storage)."""
        pass
