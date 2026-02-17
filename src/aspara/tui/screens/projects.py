"""
Projects Screen

Displays list of all projects with search and sort functionality.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

if TYPE_CHECKING:
    from aspara.catalog import ProjectInfo
    from aspara.tui.app import AsparaTUIApp

logger = logging.getLogger(__name__)


class ProjectsScreen(Screen[None]):
    """Screen displaying list of all projects."""

    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("tab", "focus_search", "Search", show=False),
        Binding("s", "toggle_sort", "Sort", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("escape", "unfocus_search", "Clear focus", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._projects: list[ProjectInfo] = []
        self._sort_key: str = "name"
        self._sort_reverse: bool = False

    @property
    def tui_app(self) -> AsparaTUIApp:
        """Get the typed app instance."""
        from aspara.tui.app import AsparaTUIApp

        assert isinstance(self.app, AsparaTUIApp)
        return self.app

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Static("Projects", classes="screen-title"),
            Input(placeholder="Search projects...", id="search-input"),
            Vertical(
                DataTable(id="projects-table", cursor_type="row"),
                classes="table-container",
            ),
            classes="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event - load projects."""
        table = self.query_one("#projects-table", DataTable)
        table.add_column("Name")
        table.add_column("Runs")
        table.add_column("Last Update")
        table.add_column("Tags")
        self._load_projects()
        self._update_column_widths()
        table.focus()

    def on_resize(self, event: events.Resize) -> None:
        """Handle resize event - adjust column widths."""
        self._update_column_widths()

    def _load_projects(self, filter_text: str = "") -> None:
        """Load and display projects.

        Args:
            filter_text: Optional filter text for project names.
        """
        try:
            self._projects = self.tui_app.project_catalog.get_projects()
        except FileNotFoundError:
            logger.debug("Data directory not found")
            self._projects = []
        except PermissionError as e:
            logger.warning("Permission denied loading projects: %s", e)
            self.notify("Permission denied", severity="error")
            self._projects = []
        except OSError as e:
            logger.error("Failed to load projects: %s", e)
            self.notify("Failed to load projects", severity="error")
            self._projects = []

        if filter_text:
            filter_lower = filter_text.lower()
            self._projects = [p for p in self._projects if filter_lower in p.name.lower()]

        self._sort_projects()
        self._update_table()

    def _sort_projects(self) -> None:
        """Sort projects by current sort key."""
        if self._sort_key == "name":
            self._projects.sort(key=lambda p: p.name.lower(), reverse=self._sort_reverse)
        elif self._sort_key == "runs":
            self._projects.sort(key=lambda p: p.run_count, reverse=self._sort_reverse)
        elif self._sort_key == "last_update":
            self._projects.sort(key=lambda p: p.last_update or datetime.min, reverse=self._sort_reverse)

    def _update_table(self) -> None:
        """Update the data table with current projects."""
        table = self.query_one("#projects-table", DataTable)
        table.clear()

        for project in self._projects:
            last_update = project.last_update.strftime("%Y-%m-%d %H:%M") if project.last_update else "-"
            tags = self._get_project_tags(project.name)
            tags_str = " ".join(f"\\[{tag}]" for tag in tags) if tags else "-"

            table.add_row(
                project.name,
                str(project.run_count),
                last_update,
                tags_str,
                key=project.name,
            )

    def _update_column_widths(self) -> None:
        """Update column widths to fill available space."""
        table = self.query_one("#projects-table", DataTable)

        # Calculate available width (subtract border/padding)
        available_width = table.size.width - 4

        if available_width <= 0 or not table.columns:
            return

        # Distribution ratios: Name(3), Runs(1), Last Update(2), Tags(4)
        ratios = [3, 1, 2, 4]
        total_ratio = sum(ratios)

        for column_key, ratio in zip(table.columns, ratios, strict=True):
            width = max(8, (available_width * ratio) // total_ratio)
            table.columns[column_key].width = width
            table.columns[column_key].auto_width = False

        table.refresh()

    def _get_project_tags(self, project_name: str) -> list[str]:
        """Get unique tags across all runs in a project.

        Args:
            project_name: Name of the project.

        Returns:
            List of unique tag names.
        """
        try:
            metadata = self.tui_app.project_catalog.get_metadata(project_name)
            return metadata.get("tags", [])
        except (FileNotFoundError, KeyError):
            return []
        except OSError as e:
            logger.debug("Failed to get tags for %s: %s", project_name, e)
            return []

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input change."""
        self._load_projects(filter_text=event.value)

    @on(DataTable.RowSelected, "#projects-table")
    def on_project_selected(self, event: DataTable.RowSelected) -> None:
        """Handle project selection."""
        if event.row_key and event.row_key.value:
            project_name = str(event.row_key.value)
            from aspara.tui.screens import RunsScreen

            self.app.push_screen(RunsScreen(project_name))

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_toggle_sort(self) -> None:
        """Toggle sort between name, runs, and last_update."""
        sort_keys = ["name", "runs", "last_update"]
        current_idx = sort_keys.index(self._sort_key)
        if self._sort_reverse:
            self._sort_key = sort_keys[(current_idx + 1) % len(sort_keys)]
            self._sort_reverse = False
        else:
            self._sort_reverse = True

        self._sort_projects()
        self._update_table()
        self.notify(f"Sorted by {self._sort_key} ({'desc' if self._sort_reverse else 'asc'})")

    def action_cursor_down(self) -> None:
        """Move cursor down in table."""
        table = self.query_one("#projects-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in table."""
        table = self.query_one("#projects-table", DataTable)
        table.action_cursor_up()

    def action_unfocus_search(self) -> None:
        """Remove focus from search input (Escape key)."""
        search_input = self.query_one("#search-input", Input)
        if search_input.has_focus:
            table = self.query_one("#projects-table", DataTable)
            table.focus()
