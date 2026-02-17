"""Tests for TUI widgets."""

from __future__ import annotations

import pytest

from aspara.tui.widgets.breadcrumb import Breadcrumb
from aspara.tui.widgets.metrics_grid import MetricsGridWidget
from aspara.tui.widgets.mini_chart import MiniChartWidget


class TestBreadcrumb:
    """Tests for Breadcrumb widget."""

    def test_render_single_item(self) -> None:
        """Test rendering a single breadcrumb item."""
        bc = Breadcrumb(["Projects"])
        rendered = bc._format_breadcrumb()
        assert "Projects" in rendered
        assert "[bold]" in rendered

    def test_render_multiple_items(self) -> None:
        """Test rendering multiple breadcrumb items."""
        bc = Breadcrumb(["Projects", "experiment-001", "run-001"])
        rendered = bc._format_breadcrumb()
        assert "Projects" in rendered
        assert "experiment-001" in rendered
        assert "run-001" in rendered
        assert " > " in rendered

    def test_render_empty_items(self) -> None:
        """Test rendering empty breadcrumb."""
        bc = Breadcrumb([])
        rendered = bc._format_breadcrumb()
        assert rendered == ""

    def test_custom_separator(self) -> None:
        """Test rendering with custom separator."""
        bc = Breadcrumb(["A", "B"], separator=" / ")
        rendered = bc._format_breadcrumb()
        assert " / " in rendered


class TestMiniChartWidget:
    """Tests for MiniChartWidget."""

    def test_init_with_data(self) -> None:
        """Test initialization with metric data."""
        steps = [1, 2, 3, 4, 5]
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        widget = MiniChartWidget("loss", steps, values)

        assert widget.metric_name == "loss"
        assert widget._steps == steps
        assert widget._values == values

    def test_init_with_empty_data(self) -> None:
        """Test initialization with empty data."""
        widget = MiniChartWidget("accuracy", [], [])

        assert widget.metric_name == "accuracy"
        assert widget._steps == []
        assert widget._values == []

    def test_can_focus_is_true(self) -> None:
        """Test that widget is focusable."""
        widget = MiniChartWidget("metric", [1], [0.5])
        assert widget.can_focus is True

    def test_downsample_short_data(self) -> None:
        """Test that short data is not downsampled."""
        steps = list(range(10))
        values = [float(i) for i in range(10)]
        widget = MiniChartWidget("metric", steps, values)

        result_steps, result_values = widget._downsample_for_display()

        assert result_steps == steps
        assert result_values == values

    def test_downsample_long_data(self) -> None:
        """Test that long data is downsampled."""
        steps = list(range(200))
        values = [float(i) for i in range(200)]
        widget = MiniChartWidget("metric", steps, values)

        result_steps, result_values = widget._downsample_for_display()

        assert len(result_steps) <= 50
        assert len(result_values) <= 50

    def test_selected_message(self) -> None:
        """Test that Selected message contains metric name."""
        msg = MiniChartWidget.Selected("test_metric")
        assert msg.metric_name == "test_metric"


@pytest.mark.asyncio
async def test_mini_chart_click_emits_selected() -> None:
    """Test that clicking emits Selected message."""
    from textual.app import App

    messages: list[MiniChartWidget.Selected] = []

    class TestApp(App[None]):
        def compose(self):
            yield MiniChartWidget("test", [1, 2, 3], [0.1, 0.2, 0.3])

        def on_mini_chart_widget_selected(self, event: MiniChartWidget.Selected) -> None:
            messages.append(event)

    app = TestApp()
    async with app.run_test() as pilot:
        widget = app.query_one(MiniChartWidget)
        widget.on_click()
        await pilot.pause()

        assert len(messages) == 1
        assert messages[0].metric_name == "test"


class TestMetricsGridWidget:
    """Tests for MetricsGridWidget."""

    def test_init_with_metrics(self) -> None:
        """Test initialization with metrics data."""
        metrics = [
            ("loss", [1, 2, 3], [0.5, 0.3, 0.1]),
            ("accuracy", [1, 2, 3], [0.6, 0.8, 0.9]),
        ]
        widget = MetricsGridWidget(metrics)

        assert widget._metrics == metrics
        assert widget._resize_timer is None

    def test_init_with_empty_metrics(self) -> None:
        """Test initialization with empty metrics."""
        widget = MetricsGridWidget([])

        assert widget._metrics == []

    def test_metric_selected_message(self) -> None:
        """Test that MetricSelected message contains metric name."""
        msg = MetricsGridWidget.MetricSelected("test_metric")
        assert msg.metric_name == "test_metric"

    def test_calculate_cols_limits_to_num_metrics(self) -> None:
        """Test that column count is limited by number of metrics."""
        # With only 2 metrics, should never exceed 2 columns
        metrics = [("m1", [1], [0.1]), ("m2", [1], [0.2])]
        widget = MetricsGridWidget(metrics)

        # Even with default width (80), cols should be limited to 2
        cols = widget._calculate_cols()
        assert cols <= len(metrics)

    def test_constants_defined(self) -> None:
        """Test that class constants are properly defined."""
        assert MetricsGridWidget.MIN_CHART_WIDTH == 40
        assert MetricsGridWidget.CHART_HEIGHT == 14
        assert MetricsGridWidget.RESIZE_DEBOUNCE_DELAY == 0.15


@pytest.mark.asyncio
async def test_metrics_grid_displays() -> None:
    """Test that MetricsGridWidget displays correctly."""
    from textual.app import App

    class TestApp(App[None]):
        def compose(self):
            metrics = [
                ("loss", [1, 2, 3], [0.5, 0.3, 0.1]),
                ("accuracy", [1, 2, 3], [0.6, 0.8, 0.9]),
            ]
            yield MetricsGridWidget(metrics, id="grid")

    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#grid", MetricsGridWidget)
        assert grid is not None
