"""
Metric Chart Screen

Displays a chart for a specific metric using textual-plotext.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static
from textual.worker import Worker, WorkerState

from aspara.exceptions import RunNotFoundError
from aspara.models import MetricRecord
from aspara.tui.app import CHART_LINE_COLOR
from aspara.tui.widgets import Breadcrumb

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aspara.tui.app import AsparaTUIApp

try:
    from textual_plotext import PlotextPlot

    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False


class MetricChartScreen(Screen[None]):
    """Screen displaying a chart for a specific metric."""

    BINDINGS = [
        Binding("h", "pan_left", "Pan Left", show=True),
        Binding("l", "pan_right", "Pan Right", show=True),
        Binding("left", "pan_left", "Pan Left", show=False),
        Binding("right", "pan_right", "Pan Right", show=False),
        Binding("plus", "zoom_in", "Zoom In", show=True),
        Binding("equals", "zoom_in", "Zoom In", show=False),
        Binding("minus", "zoom_out", "Zoom Out", show=True),
        Binding("r", "reset_view", "Reset", show=True),
        Binding("w", "toggle_watch", "Watch", show=True),
        Binding("backspace", "go_back", "Back", show=False),
    ]

    def __init__(self, project_name: str, run_name: str, metric_name: str) -> None:
        super().__init__()
        self._project_name = project_name
        self._run_name = run_name
        self._metric_name = metric_name
        self._steps: list[int] = []
        self._values: list[float] = []
        self._view_start: int | None = None
        self._view_end: int | None = None
        self._watching: bool = False
        self._watch_worker: Worker | None = None
        self._last_timestamp: datetime = datetime.now(timezone.utc)

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
            Breadcrumb(["Projects", self._project_name, self._run_name, self._metric_name]),
            Vertical(
                self._create_chart_widget(),
                id="chart-container",
                classes="chart-container",
            ),
            Static(id="current-value", classes="current-value"),
            Static(id="watch-status", classes="watch-status"),
            classes="main-container",
        )
        yield Footer()

    def _create_chart_widget(self) -> Static | PlotextPlot:
        """Create the chart widget.

        Returns:
            PlotextPlot if available, otherwise a Static placeholder.
        """
        if HAS_PLOTEXT:
            return PlotextPlot(id="chart")
        else:
            return Static("textual-plotext not installed. Install with: pip install textual-plotext", id="chart")

    def on_mount(self) -> None:
        """Handle mount event - load metric data."""
        self._load_metric_data()
        self._update_chart()

    def _load_metric_data(self) -> None:
        """Load metric data from catalog."""
        try:
            df = self.tui_app.run_catalog.load_metrics(self._project_name, self._run_name)
            if df is not None and len(df) > 0 and self._metric_name in df.columns:
                filtered = df.filter(df[self._metric_name].is_not_null())
                if len(filtered) > 0:
                    if "step" in filtered.columns:
                        steps = filtered["step"].to_list()
                        self._steps = [s if s is not None else i for i, s in enumerate(steps)]
                    else:
                        self._steps = list(range(len(filtered)))
                    self._values = filtered[self._metric_name].to_list()

                    if "timestamp" in filtered.columns:
                        timestamps = filtered["timestamp"].to_list()
                        if timestamps:
                            last_ts = timestamps[-1]
                            if last_ts is not None:
                                self._last_timestamp = last_ts

                    self._apply_lttb_if_needed()
        except (FileNotFoundError, RunNotFoundError):
            logger.debug("Metric data not found for %s/%s", self._project_name, self._run_name)
        except OSError as e:
            logger.error("Failed to load metric data: %s", e)
            self.notify("Failed to load metric data", severity="error")

    def _apply_lttb_if_needed(self) -> None:
        """Apply LTTB downsampling if data is large."""
        threshold = 1000
        if len(self._steps) > threshold:
            try:
                from lttb import downsample

                data = list(zip(self._steps, self._values, strict=True))
                downsampled = downsample(data, threshold)
                self._steps = [int(d[0]) for d in downsampled]
                self._values = [float(d[1]) for d in downsampled]
            except ImportError:
                pass

    def _update_chart(self) -> None:
        """Update the chart display."""
        if not HAS_PLOTEXT:
            return

        chart = self.query_one("#chart", PlotextPlot)

        if not self._steps or not self._values:
            chart.plt.clear_figure()
            chart.plt.title("No data")
            chart.refresh()
            return

        view_steps = self._steps
        view_values = self._values
        if self._view_start is not None and self._view_end is not None:
            indices = [i for i, s in enumerate(self._steps) if self._view_start <= s <= self._view_end]
            if indices:
                view_steps = [self._steps[i] for i in indices]
                view_values = [self._values[i] for i in indices]

        chart.plt.clear_figure()
        chart.plt.title(self._metric_name)
        chart.plt.xlabel("step")
        chart.plt.plot(view_steps, view_values, color=CHART_LINE_COLOR)
        chart.refresh()

        if self._values:
            current_step = self._steps[-1] if self._steps else 0
            current_value = self._values[-1]
            value_widget = self.query_one("#current-value", Static)
            value_widget.update(f"Current: step={current_step}, value={current_value:.6g}")

    def _get_view_range(self) -> tuple[int, int]:
        """Get current view range.

        Returns:
            Tuple of (start, end) step values.
        """
        if self._view_start is not None and self._view_end is not None:
            return (self._view_start, self._view_end)
        if self._steps:
            return (min(self._steps), max(self._steps))
        return (0, 100)

    def action_pan_left(self) -> None:
        """Pan chart view left."""
        if not self._steps:
            return

        start, end = self._get_view_range()
        width = end - start
        pan_amount = max(1, width // 10)

        new_start = max(min(self._steps), start - pan_amount)
        new_end = new_start + width

        self._view_start = new_start
        self._view_end = new_end
        self._update_chart()

    def action_pan_right(self) -> None:
        """Pan chart view right."""
        if not self._steps:
            return

        start, end = self._get_view_range()
        width = end - start
        pan_amount = max(1, width // 10)

        new_end = min(max(self._steps), end + pan_amount)
        new_start = new_end - width

        self._view_start = new_start
        self._view_end = new_end
        self._update_chart()

    def action_zoom_in(self) -> None:
        """Zoom in on chart."""
        if not self._steps:
            return

        start, end = self._get_view_range()
        width = end - start
        if width <= 10:
            return

        center = (start + end) // 2
        new_width = max(10, width // 2)

        self._view_start = center - new_width // 2
        self._view_end = center + new_width // 2
        self._update_chart()

    def action_zoom_out(self) -> None:
        """Zoom out on chart."""
        if not self._steps:
            return

        start, end = self._get_view_range()
        width = end - start
        center = (start + end) // 2
        new_width = width * 2

        min_step = min(self._steps)
        max_step = max(self._steps)

        self._view_start = max(min_step, center - new_width // 2)
        self._view_end = min(max_step, center + new_width // 2)

        if self._view_start == min_step and self._view_end == max_step:
            self._view_start = None
            self._view_end = None

        self._update_chart()

    def action_reset_view(self) -> None:
        """Reset chart view to show all data."""
        self._view_start = None
        self._view_end = None
        self._update_chart()

    def action_toggle_watch(self) -> None:
        """Toggle live watch mode."""
        self._watching = not self._watching
        status_widget = self.query_one("#watch-status", Static)

        if self._watching:
            status_widget.update("[green]● Watching for updates...[/]")
            self._start_watching()
        else:
            status_widget.update("")
            self._stop_watching()

    def _start_watching(self) -> None:
        """Start watching for metric updates."""
        self._watch_worker = self.run_worker(self._watch_metrics(), exclusive=True)

    def _stop_watching(self) -> None:
        """Stop watching for metric updates."""
        if self._watch_worker is not None and self._watch_worker.state == WorkerState.RUNNING:
            self._watch_worker.cancel()
            self._watch_worker = None

    async def _watch_metrics(self) -> None:
        """Watch for metric updates using catalog subscribe."""
        try:
            async for record in self.tui_app.run_catalog.subscribe(
                {self._project_name: [self._run_name]},
                self._last_timestamp,
            ):
                if isinstance(record, MetricRecord) and self._metric_name in record.metrics:
                    value = record.metrics[self._metric_name]
                    step = record.step if record.step is not None else len(self._steps)

                    self._steps.append(step)
                    self._values.append(float(value))
                    self._last_timestamp = record.timestamp

                    self._apply_lttb_if_needed()
                    self.app.call_from_thread(self._update_chart)

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except (FileNotFoundError, RunNotFoundError):
            logger.debug("Watch stopped: data not found")
        except OSError as e:
            logger.warning("Watch stopped due to error: %s", e)

    def on_unmount(self) -> None:
        """Handle unmount - stop watching."""
        self._stop_watching()

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()
