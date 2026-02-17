"""
Runs Screen

Displays list of runs for a specific project.
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

from aspara.exceptions import ProjectNotFoundError
from aspara.models import RunStatus
from aspara.tui.widgets import Breadcrumb

if TYPE_CHECKING:
    from aspara.catalog import RunInfo
    from aspara.tui.app import AsparaTUIApp

logger = logging.getLogger(__name__)


class RunsScreen(Screen[None]):
    """Screen displaying list of runs for a project."""

    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("tab", "focus_search", "Search", show=False),
        Binding("s", "toggle_sort", "Sort", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("backspace", "go_back", "Back", show=False),
        Binding("escape", "unfocus_search", "Clear focus", show=False),
    ]

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self._project_name = project_name
        self._runs: list[RunInfo] = []
        self._sort_key: str = "last_update"
        self._sort_reverse: bool = True

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
            Breadcrumb(["Projects", self._project_name]),
            Input(placeholder="Search runs...", id="search-input"),
            Vertical(
                DataTable(id="runs-table", cursor_type="row"),
                classes="table-container",
            ),
            Static(
                "Status: [yellow]●[/] Running  [green]✓[/] Completed  [red]✗[/] Failed  [yellow]?[/] Maybe Failed",
                classes="status-legend",
            ),
            classes="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event - load runs."""
        table = self.query_one("#runs-table", DataTable)
        table.add_column("Status")
        table.add_column("Name")
        table.add_column("Last Update")
        table.add_column("Tags")
        self._load_runs()
        self._update_column_widths()
        table.focus()

    def on_resize(self, event: events.Resize) -> None:
        """Handle resize event - adjust column widths."""
        self._update_column_widths()

    def _update_column_widths(self) -> None:
        """Update column widths to fill available space."""
        table = self.query_one("#runs-table", DataTable)

        # Calculate available width (subtract border/padding)
        available_width = table.size.width - 4

        if available_width <= 0 or not table.columns:
            return

        # Distribution ratios: Status(1), Name(3), Last Update(2), Tags(3)
        ratios = [1, 3, 2, 3]
        total_ratio = sum(ratios)

        for column_key, ratio in zip(table.columns, ratios, strict=True):
            width = max(6, (available_width * ratio) // total_ratio)
            table.columns[column_key].width = width
            table.columns[column_key].auto_width = False

        table.refresh()

    def _load_runs(self, filter_text: str = "") -> None:
        """Load and display runs.

        Args:
            filter_text: Optional filter text for run names.
        """
        try:
            self._runs = self.tui_app.run_catalog.get_runs(self._project_name)
        except ProjectNotFoundError:
            logger.debug("Project not found: %s", self._project_name)
            self._runs = []
        except FileNotFoundError:
            logger.debug("Data directory not found")
            self._runs = []
        except PermissionError as e:
            logger.warning("Permission denied loading runs: %s", e)
            self.notify("Permission denied", severity="error")
            self._runs = []
        except OSError as e:
            logger.error("Failed to load runs: %s", e)
            self.notify("Failed to load runs", severity="error")
            self._runs = []

        if filter_text:
            filter_lower = filter_text.lower()
            self._runs = [r for r in self._runs if filter_lower in r.name.lower()]

        self._sort_runs()
        self._update_table()

    def _sort_runs(self) -> None:
        """Sort runs by current sort key."""
        if self._sort_key == "name":
            self._runs.sort(key=lambda r: r.name.lower(), reverse=self._sort_reverse)
        elif self._sort_key == "last_update":
            self._runs.sort(key=lambda r: r.last_update or datetime.min, reverse=self._sort_reverse)
        elif self._sort_key == "status":
            status_order = {
                RunStatus.WIP: 0,
                RunStatus.COMPLETED: 1,
                RunStatus.MAYBE_FAILED: 2,
                RunStatus.FAILED: 3,
            }
            self._runs.sort(key=lambda r: status_order.get(r.status, 99), reverse=self._sort_reverse)

    def _update_table(self) -> None:
        """Update the data table with current runs."""
        table = self.query_one("#runs-table", DataTable)
        table.clear()

        for run in self._runs:
            status_icon = self._get_status_icon(run.status)
            last_update = run.last_update.strftime("%Y-%m-%d %H:%M") if run.last_update else "-"
            tags_str = " ".join(f"\\[{tag}]" for tag in run.tags) if run.tags else "-"

            table.add_row(
                status_icon,
                run.name,
                last_update,
                tags_str,
                key=run.name,
            )

    def _get_status_icon(self, status: RunStatus) -> str:
        """Get status icon with color markup.

        Args:
            status: Run status.

        Returns:
            Colored status icon string.
        """
        icons = {
            RunStatus.WIP: "[yellow]●[/]",
            RunStatus.COMPLETED: "[green]✓[/]",
            RunStatus.FAILED: "[red]✗[/]",
            RunStatus.MAYBE_FAILED: "[yellow]?[/]",
        }
        return icons.get(status, "[white]?[/]")

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input change."""
        self._load_runs(filter_text=event.value)

    @on(DataTable.RowSelected, "#runs-table")
    def on_run_selected(self, event: DataTable.RowSelected) -> None:
        """Handle run selection."""
        if event.row_key and event.row_key.value:
            run_name = str(event.row_key.value)
            from aspara.tui.screens import RunDetailScreen

            self.app.push_screen(RunDetailScreen(self._project_name, run_name))

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_toggle_sort(self) -> None:
        """Toggle sort between name, metrics, last_update, and status."""
        sort_keys = ["last_update", "name", "status"]
        current_idx = sort_keys.index(self._sort_key)
        if self._sort_reverse:
            self._sort_key = sort_keys[(current_idx + 1) % len(sort_keys)]
            self._sort_reverse = False
        else:
            self._sort_reverse = True

        self._sort_runs()
        self._update_table()
        self.notify(f"Sorted by {self._sort_key} ({'desc' if self._sort_reverse else 'asc'})")

    def action_cursor_down(self) -> None:
        """Move cursor down in table."""
        table = self.query_one("#runs-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in table."""
        table = self.query_one("#runs-table", DataTable)
        table.action_cursor_up()

    def action_go_back(self) -> None:
        """Go back to previous screen if not editing."""
        if isinstance(self.app.focused, Input):
            return  # Let Input handle backspace
        self.app.pop_screen()

    def action_unfocus_search(self) -> None:
        """Remove focus from search input (Escape key)."""
        search_input = self.query_one("#search-input", Input)
        if search_input.has_focus:
            table = self.query_one("#runs-table", DataTable)
            table.focus()
