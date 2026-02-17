"""
Metrics Grid Widget

A widget that displays multiple metrics in a grid layout using individual PlotextPlot widgets.
This solves the xticks/xlabel truncation issue that occurs with ItemGrid.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.dom import DOMNode
from textual.events import Click, Resize
from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static

from aspara.tui.app import CHART_LINE_COLOR

try:
    from textual_plotext import PlotextPlot

    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False


class _ChartCell(Widget):
    """A single chart cell in the metrics grid."""

    can_focus = True

    class Selected(Message):
        """Message sent when the chart cell is selected."""

        def __init__(self, metric_name: str) -> None:
            """Initialize the Selected message.

            Args:
                metric_name: The name of the selected metric.
            """
            self.metric_name = metric_name
            super().__init__()

    def __init__(
        self,
        metric_name: str,
        steps: list[int],
        values: list[float],
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._metric_name = metric_name
        self._steps = steps
        self._values = values
        self._plot: PlotextPlot | None = None

    @property
    def metric_name(self) -> str:
        """Get the metric name."""
        return self._metric_name

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        if HAS_PLOTEXT:
            self._plot = PlotextPlot()
            yield self._plot
        else:
            yield Static(f"{self._metric_name}: No plotext")

    def on_mount(self) -> None:
        """Handle mount event - render the chart."""
        self._render_chart()

    def _render_chart(self) -> None:
        """Render the chart with current data."""
        if not HAS_PLOTEXT or self._plot is None:
            return

        self._plot.plt.clear_figure()

        if self._steps and self._values:
            display_steps, display_values = self._downsample_for_display()

            current_value = self._values[-1]
            if isinstance(current_value, float):
                value_str = f"{current_value:.4g}"
            else:
                value_str = str(current_value)

            display_name = self._metric_name.lstrip("_")
            self._plot.plt.title(f"{display_name} = {value_str}")
            self._plot.plt.plot(display_steps, display_values, color=CHART_LINE_COLOR)

            # Set xticks to show step range
            if len(display_steps) >= 2:
                min_step = display_steps[0]
                max_step = display_steps[-1]
                self._plot.plt.xticks([min_step, max_step])
        else:
            display_name = self._metric_name.lstrip("_")
            self._plot.plt.title(f"{display_name} (no data)")

        self._plot.refresh()

    def _downsample_for_display(self) -> tuple[list[int], list[float]]:
        """Downsample data for mini chart display.

        Returns:
            Tuple of (steps, values) downsampled if necessary.
        """
        max_points = 50
        if len(self._steps) <= max_points:
            return self._steps, self._values

        try:
            import numpy as np
            from lttb import downsample

            data = np.array(list(zip(self._steps, self._values, strict=True)))
            downsampled = downsample(data, max_points)
            return (
                [int(d[0]) for d in downsampled],
                [float(d[1]) for d in downsampled],
            )
        except ImportError:
            step = len(self._steps) // max_points
            return self._steps[::step], self._values[::step]

    def key_enter(self) -> None:
        """Handle Enter key press."""
        self.post_message(self.Selected(self._metric_name))


class MetricsGridWidget(Widget):
    """A widget that displays multiple metrics in a responsive grid.

    Uses individual PlotextPlot widgets arranged in Horizontal containers
    to ensure proper xticks display.

    Attributes:
        MIN_CHART_WIDTH: Minimum column width in characters (for xticks visibility).
        CHART_HEIGHT: Height per chart in terminal lines.
        RESIZE_DEBOUNCE_DELAY: Delay in seconds before processing resize events.
    """

    MIN_CHART_WIDTH = 40
    CHART_HEIGHT = 14
    RESIZE_DEBOUNCE_DELAY = 0.15

    _cols = reactive(1)

    class MetricSelected(Message):
        """Message sent when a metric chart is clicked."""

        def __init__(self, metric_name: str) -> None:
            """Initialize the MetricSelected message.

            Args:
                metric_name: The name of the selected metric.
            """
            self.metric_name = metric_name
            super().__init__()

    def __init__(
        self,
        metrics: list[tuple[str, list[int], list[float]]],
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the MetricsGridWidget.

        Args:
            metrics: List of tuples (metric_name, steps, values).
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._metrics = metrics
        self._resize_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        if not self._metrics:
            yield Static("No metrics available")
            return

        yield Vertical(id="metrics-rows")

    def on_mount(self) -> None:
        """Handle mount event - build the grid."""
        self._rebuild_grid()

    def on_resize(self, event: Resize) -> None:
        """Handle resize event - recalculate grid dimensions with debounce."""
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(self.RESIZE_DEBOUNCE_DELAY, self._handle_debounced_resize)

    def _handle_debounced_resize(self) -> None:
        """Handle debounced resize - rebuild grid if column count changed."""
        self._resize_timer = None
        new_cols = self._calculate_cols()
        if new_cols != self._cols:
            self._cols = new_cols
            self._rebuild_grid()

    def _calculate_cols(self) -> int:
        """Calculate optimal column count based on widget width.

        Returns:
            Number of columns for the grid layout.
        """
        width = self.size.width if self.size.width > 0 else 80
        cols = max(1, width // self.MIN_CHART_WIDTH)
        cols = min(cols, len(self._metrics))
        return cols

    def _rebuild_grid(self) -> None:
        """Rebuild the grid with current column count."""
        if not self._metrics:
            return

        try:
            container = self.query_one("#metrics-rows", Vertical)
        except Exception:
            return

        # Remove existing rows
        container.remove_children()

        cols = self._calculate_cols()
        rows_count = (len(self._metrics) + cols - 1) // cols

        # Update container height
        self.styles.height = rows_count * self.CHART_HEIGHT + 2

        # Create rows with cells
        for row_idx in range(rows_count):
            start_idx = row_idx * cols
            end_idx = min(start_idx + cols, len(self._metrics))

            # Create cells for this row
            cells = []
            for i in range(start_idx, end_idx):
                name, steps, values = self._metrics[i]
                cell = _ChartCell(name, steps, values, id=f"chart-cell-{i}", classes="chart-cell")
                cells.append(cell)

            # Create row with cells as children
            row = Horizontal(*cells, classes="metrics-row")
            container.mount(row)

    @staticmethod
    def _get_metric_name_from_cell(cell: _ChartCell) -> str:
        """Get metric name from a chart cell."""
        return cell.metric_name

    def on_click(self, event: Click) -> None:
        """Handle click event - determine which metric was clicked.

        Args:
            event: The click event.
        """
        # Find clicked chart cell by traversing the widget tree
        target: DOMNode | None = event.widget
        while target is not None and target is not self:
            if isinstance(target, _ChartCell):
                self.post_message(self.MetricSelected(target.metric_name))
                return
            target = target.parent

    @on(_ChartCell.Selected)
    def _on_cell_selected(self, event: _ChartCell.Selected) -> None:
        """Handle cell selection and propagate as MetricSelected.

        Args:
            event: The cell selected event.
        """
        self.post_message(self.MetricSelected(event.metric_name))
