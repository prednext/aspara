"""Configuration object for run parameters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Config:
    """Configuration object that allows attribute-style access to parameters.

    Similar to wandb.config, this class provides a dict-like object that
    can be accessed via attributes.
    """

    def __init__(self, data: dict[str, Any] | None = None, on_change: Callable[[], None] | None = None) -> None:
        """Initialize config with optional initial data.

        Args:
            data: Optional dictionary of initial configuration values
            on_change: Optional callback function called when config changes
        """
        object.__setattr__(self, "_data", data or {})
        object.__setattr__(self, "_on_change", on_change)

    def __getattr__(self, name: str) -> Any:
        """Get config value by attribute name."""
        data = object.__getattribute__(self, "_data")
        if name in data:
            return data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """Set config value by attribute name."""
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value
            self._notify()

    def __getitem__(self, key: str) -> Any:
        """Get config value by key."""
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set config value by key."""
        self._data[key] = value
        self._notify()

    def __contains__(self, key: str) -> bool:
        """Check if key exists in config."""
        return key in self._data

    def __repr__(self) -> str:
        """Return string representation of config."""
        return f"Config({self._data})"

    def keys(self) -> Any:
        """Return config keys."""
        return self._data.keys()

    def values(self) -> Any:
        """Return config values."""
        return self._data.values()

    def items(self) -> Any:
        """Return config items."""
        return self._data.items()

    def update(self, data: dict[str, Any]) -> None:
        """Update config with dictionary of values.

        Args:
            data: Dictionary of configuration values to update
        """
        self._data.update(data)
        self._notify()

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary containing all configuration values
        """
        return dict(self._data)

    def _notify(self) -> None:
        """Notify about config change via callback."""
        if self._on_change:
            self._on_change()
