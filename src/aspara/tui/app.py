"""
Aspara TUI Application

Main application class for the terminal-based dashboard.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding
from textual.theme import Theme

from aspara.catalog import ProjectCatalog, RunCatalog
from aspara.config import get_data_dir

# Chart line color - calm asparagus green matching the brand palette
CHART_LINE_COLOR = (90, 139, 111)

# Aspara theme (matching web dashboard color palette)
ASPARA_THEME = Theme(
    name="aspara",
    primary="#2C2520",
    secondary="#8B7F75",
    accent="#CC785C",
    foreground="#2C2520",
    background="#F5F3F0",
    surface="#FDFCFB",
    panel="#E6E3E0",
    success="#5A8B6F",
    error="#C84C3C",
    warning="#D4864E",
)


class AsparaTUIApp(App[None]):
    """Aspara Terminal UI Application.

    A terminal-based dashboard for viewing projects, runs, and metrics.
    """

    TITLE = "Aspara TUI"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True, priority=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("escape", "back", "Back", show=True),
    ]

    def __init__(self, data_dir: str | None = None) -> None:
        """Initialize the TUI application.

        Args:
            data_dir: Data directory path. Defaults to XDG-based default.
        """
        super().__init__()
        self._data_dir = Path(data_dir) if data_dir else get_data_dir()
        self._project_catalog: ProjectCatalog | None = None
        self._run_catalog: RunCatalog | None = None

        # Register and apply Aspara theme
        self.register_theme(ASPARA_THEME)
        self.theme = "aspara"

    @property
    def data_dir(self) -> Path:
        """Get the data directory path."""
        return self._data_dir

    @property
    def project_catalog(self) -> ProjectCatalog:
        """Get or create the project catalog instance."""
        if self._project_catalog is None:
            self._project_catalog = ProjectCatalog(self._data_dir)
        return self._project_catalog

    @property
    def run_catalog(self) -> RunCatalog:
        """Get or create the run catalog instance."""
        if self._run_catalog is None:
            self._run_catalog = RunCatalog(self._data_dir)
        return self._run_catalog

    def on_mount(self) -> None:
        """Handle mount event - push the initial screen."""
        from aspara.tui.screens import ProjectsScreen

        self.push_screen(ProjectsScreen())

    async def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_help(self) -> None:
        """Show help screen."""
        from aspara.tui.screens import HelpScreen

        self.push_screen(HelpScreen())

    async def action_back(self) -> None:
        """Go back to previous screen."""
        if len(self.screen_stack) > 1:
            self.pop_screen()
