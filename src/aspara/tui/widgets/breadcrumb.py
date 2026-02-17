"""
Breadcrumb Widget

Navigation breadcrumb showing current location in the hierarchy.
"""

from __future__ import annotations

from textual.widgets import Static


class Breadcrumb(Static):
    """Breadcrumb navigation widget.

    Displays a path-like navigation trail like:
    Projects > experiment-001 > run-001
    """

    DEFAULT_CSS = """
    Breadcrumb {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    """

    def __init__(self, items: list[str], separator: str = " > ") -> None:
        """Initialize the breadcrumb.

        Args:
            items: List of breadcrumb items.
            separator: Separator string between items.
        """
        self._items = items
        self._separator = separator
        super().__init__(self._format_breadcrumb())

    def _format_breadcrumb(self) -> str:
        """Format the breadcrumb text.

        Returns:
            Formatted breadcrumb string.
        """
        if not self._items:
            return ""

        parts = []
        for i, item in enumerate(self._items):
            if i == len(self._items) - 1:
                parts.append(f"[bold]{item}[/bold]")
            else:
                parts.append(f"[dim]{item}[/dim]")

        return self._separator.join(parts)

    def update_items(self, items: list[str]) -> None:
        """Update breadcrumb items.

        Args:
            items: New list of breadcrumb items.
        """
        self._items = items
        self.update(self._format_breadcrumb())
