"""
Run Detail Screen

Displays detailed information about a specific run.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from aspara.exceptions import RunNotFoundError
from aspara.models import RunStatus
from aspara.tui.widgets import Breadcrumb, MetricsGridWidget

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aspara.catalog import RunInfo
    from aspara.tui.app import AsparaTUIApp


class RunDetailScreen(Screen[None]):
    """Screen displaying details of a specific run."""

    BINDINGS = [
        Binding("backspace", "go_back", "Back", show=False),
    ]

    def __init__(self, project_name: str, run_name: str) -> None:
        super().__init__()
        self._project_name = project_name
        self._run_name = run_name
        self._run_info: RunInfo | None = None
        self._metrics: dict[str, float] = {}

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
            Breadcrumb(["Projects", self._project_name, self._run_name]),
            Horizontal(
                Vertical(
                    Static("Run Info", classes="section-title"),
                    Static(id="run-info-content", classes="info-content"),
                    classes="info-panel",
                ),
                Vertical(
                    Static("Parameters", classes="section-title"),
                    Static(id="params-content", classes="info-content"),
                    classes="info-panel",
                ),
                classes="info-row",
            ),
            Vertical(
                Static("Metrics (Click to view detail)", classes="section-title"),
                VerticalScroll(
                    Container(id="metrics-grid-container"),
                    classes="metrics-scroll",
                ),
                classes="metrics-container",
            ),
            classes="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event - load run details."""
        self._load_run_info()
        self._load_metrics()

    def _load_run_info(self) -> None:
        """Load and display run information."""
        try:
            self._run_info = self.tui_app.run_catalog.get(self._project_name, self._run_name)
        except RunNotFoundError:
            logger.debug("Run not found: %s/%s", self._project_name, self._run_name)
            self._run_info = None
        except FileNotFoundError:
            logger.debug("Data file not found for run: %s/%s", self._project_name, self._run_name)
            self._run_info = None
        except OSError as e:
            logger.error("Failed to load run info: %s", e)
            self.notify("Failed to load run info", severity="error")
            self._run_info = None

        info_widget = self.query_one("#run-info-content", Static)

        if self._run_info is None:
            info_widget.update("Run not found")
            return

        status_text = self._get_status_text(self._run_info.status)
        tags = self._run_info.tags
        tags_text = " ".join(f"[{tag}]" for tag in tags) if tags else "-"

        notes = self._get_run_notes()
        notes_text = notes[:100] + "..." if len(notes) > 100 else notes if notes else "-"

        info_widget.update(f"Status: {status_text}\nTags: {tags_text}\nNote: {notes_text}")

        params_widget = self.query_one("#params-content", Static)
        params = self._get_run_params()
        if params:
            params_text = "\n".join(f"{k}: {v}" for k, v in list(params.items())[:10])
            if len(params) > 10:
                params_text += f"\n... and {len(params) - 10} more"
        else:
            params_text = "-"
        params_widget.update(params_text)

    def _get_status_text(self, status: RunStatus) -> str:
        """Get colored status text.

        Args:
            status: Run status.

        Returns:
            Colored status text.
        """
        icons = {
            RunStatus.WIP: "[yellow]● Running[/]",
            RunStatus.COMPLETED: "[green]✓ Completed[/]",
            RunStatus.FAILED: "[red]✗ Failed[/]",
            RunStatus.MAYBE_FAILED: "[yellow]? Maybe Failed[/]",
        }
        return icons.get(status, "Unknown")

    def _get_run_notes(self) -> str:
        """Get notes from run metadata.

        Returns:
            Notes string or empty string.
        """
        try:
            metadata = self.tui_app.run_catalog.get_metadata(self._project_name, self._run_name)
            return metadata.get("notes", "")
        except (FileNotFoundError, KeyError, RunNotFoundError):
            return ""
        except OSError as e:
            logger.debug("Failed to get notes for %s/%s: %s", self._project_name, self._run_name, e)
            return ""

    def _get_run_params(self) -> dict[str, str]:
        """Get parameters from run metadata.

        Returns:
            Dictionary of parameters.
        """
        try:
            metadata = self.tui_app.run_catalog.get_metadata(self._project_name, self._run_name)
            return metadata.get("params", {})
        except (FileNotFoundError, KeyError, RunNotFoundError):
            return {}
        except OSError as e:
            logger.debug("Failed to get params for %s/%s: %s", self._project_name, self._run_name, e)
            return {}

    def _load_metrics(self) -> None:
        """Load and display metrics as a subplot grid."""
        container = self.query_one("#metrics-grid-container", Container)
        metrics_data: list[tuple[str, list[int], list[float]]] = []

        try:
            df = self.tui_app.run_catalog.load_metrics(self._project_name, self._run_name)
            if df is not None and len(df) > 0:
                metric_cols = [c for c in df.columns if c not in ("timestamp", "step")]

                for col in sorted(metric_cols):
                    filtered = df.filter(df[col].is_not_null())
                    if len(filtered) == 0:
                        continue

                    if "step" in filtered.columns:
                        steps_raw = filtered["step"].to_list()
                        steps = [s if s is not None else i for i, s in enumerate(steps_raw)]
                    else:
                        steps = list(range(len(filtered)))

                    values = filtered[col].to_list()
                    values = [float(v) if v is not None else 0.0 for v in values]

                    if values:
                        self._metrics[col] = values[-1]
                        metrics_data.append((col, steps, values))
        except (FileNotFoundError, RunNotFoundError):
            logger.debug("Metrics not found for %s/%s", self._project_name, self._run_name)
        except OSError as e:
            logger.error("Failed to load metrics: %s", e)
            self.notify("Failed to load metrics", severity="error")

        if metrics_data:
            grid = MetricsGridWidget(metrics_data, id="metrics-grid")
            container.mount(grid)
        else:
            container.mount(Static("No metrics available", id="no-metrics"))

    @on(MetricsGridWidget.MetricSelected)
    def on_chart_selected(self, event: MetricsGridWidget.MetricSelected) -> None:
        """Handle chart selection."""
        from aspara.tui.screens.metric_chart import MetricChartScreen

        self.app.push_screen(MetricChartScreen(self._project_name, self._run_name, event.metric_name))

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()
