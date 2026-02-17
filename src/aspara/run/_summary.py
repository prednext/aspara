"""Summary object for storing final run results."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Summary:
    """Summary object for storing final run results.

    Similar to wandb.run.summary, this class stores the final values
    for a run (e.g., best accuracy, final loss).
    """

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        """Initialize summary with optional callback.

        Args:
            on_change: Optional callback function called when summary changes
        """
        self._on_change = on_change
        self._data: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        """Get summary value by key."""
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set summary value by key and write to file."""
        self._data[key] = value
        self._notify()

    def __contains__(self, key: str) -> bool:
        """Check if key exists in summary."""
        return key in self._data

    def __repr__(self) -> str:
        """Return string representation of summary."""
        return f"Summary({self._data})"

    def update(self, data: dict[str, Any]) -> None:
        """Update summary with dictionary of values.

        Args:
            data: Dictionary of summary values to update
        """
        self._data.update(data)
        self._notify()

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary.

        Returns:
            Dictionary containing all summary values
        """
        return dict(self._data)

    def _notify(self) -> None:
        """Notify about summary change via callback."""
        if self._on_change:
            self._on_change()
