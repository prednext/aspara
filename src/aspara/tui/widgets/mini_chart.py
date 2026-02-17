"""
Mini Chart Widget

A small chart widget for displaying metric data in a grid layout.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from aspara.tui.app import CHART_LINE_COLOR

try:
    from textual_plotext import PlotextPlot

    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False


class MiniChartWidget(Widget):
    """A small chart widget for displaying a single metric.

    Attributes:
        metric_name: Name of the metric being displayed.
        steps: List of step values (x-axis).
        values: List of metric values (y-axis).
    """

    can_focus = True

    class Selected(Message):
        """Message sent when the chart is selected."""

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
        """Initialize the MiniChartWidget.

        Args:
            metric_name: Name of the metric.
            steps: List of step values.
            values: List of metric values.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
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

            # Include step range in title (always visible even in small charts)
            if len(display_steps) >= 2:
                step_info = f"step {display_steps[0]}-{display_steps[-1]}"
            else:
                step_info = f"step {display_steps[0]}" if display_steps else ""
            title = f"{self._metric_name} ({step_info}) = {value_str}"
            self._plot.plt.title(title)

            self._plot.plt.plot(display_steps, display_values, color=CHART_LINE_COLOR)
        else:
            self._plot.plt.title(f"{self._metric_name} (no data)")

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

    def on_click(self) -> None:
        """Handle click event."""
        self.post_message(self.Selected(self._metric_name))

    def action_select(self) -> None:
        """Action to select this chart (triggered by Enter key)."""
        self.post_message(self.Selected(self._metric_name))

    def key_enter(self) -> None:
        """Handle Enter key press."""
        self.post_message(self.Selected(self._metric_name))
