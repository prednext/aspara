"""Tests for TUI screens."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input

from aspara.tui.app import AsparaTUIApp
from aspara.tui.screens import HelpScreen, ProjectsScreen, RunDetailScreen
from aspara.tui.screens.metric_chart import MetricChartScreen


@pytest.fixture
def app(tmp_path):
    """Create app with temporary data directory."""
    return AsparaTUIApp(data_dir=str(tmp_path))


class TestProjectsScreen:
    """Tests for ProjectsScreen."""

    @pytest.mark.asyncio
    async def test_projects_screen_displays(self, app: AsparaTUIApp) -> None:
        """Test that projects screen displays correctly."""
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, ProjectsScreen)
            table = app.screen.query_one("#projects-table")
            assert table is not None

    @pytest.mark.asyncio
    async def test_projects_screen_has_search_input(self, app: AsparaTUIApp) -> None:
        """Test that projects screen has search input."""
        async with app.run_test() as pilot:
            await pilot.pause()
            search_input = app.screen.query_one("#search-input")
            assert search_input is not None

    @pytest.mark.asyncio
    async def test_help_screen_opens(self, app: AsparaTUIApp) -> None:
        """Test that help screen opens with action_help."""
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_help()
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_quit_action(self, app: AsparaTUIApp) -> None:
        """Test that q key quits the app."""
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_focus_search_with_slash(self, app: AsparaTUIApp) -> None:
        """Test that slash key focuses search input."""
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()

            search_input = app.screen.query_one("#search-input", Input)
            assert search_input.has_focus

    @pytest.mark.asyncio
    async def test_unfocus_search_with_escape(self, app: AsparaTUIApp) -> None:
        """Test that Escape key unfocuses search input."""
        async with app.run_test() as pilot:
            await pilot.pause()
            # First focus the search
            await pilot.press("slash")
            await pilot.pause()

            search_input = app.screen.query_one("#search-input", Input)
            assert search_input.has_focus

            # Then press Escape to unfocus
            await pilot.press("escape")
            await pilot.pause()

            assert not search_input.has_focus

    @pytest.mark.asyncio
    async def test_sort_toggle(self, app: AsparaTUIApp) -> None:
        """Test that s key toggles sort."""
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ProjectsScreen)

            initial_sort_key = screen._sort_key
            initial_reverse = screen._sort_reverse

            await pilot.press("s")
            await pilot.pause()

            # Sort should have changed (either key or direction)
            assert screen._sort_key != initial_sort_key or screen._sort_reverse != initial_reverse

    @pytest.mark.asyncio
    async def test_cursor_navigation_j_k(self, app: AsparaTUIApp) -> None:
        """Test that j/k keys move cursor in table."""
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.screen.query_one("#projects-table", DataTable)

            # Ensure table has focus
            table.focus()
            await pilot.pause()

            # j should move down, k should move up
            # These should not raise errors even with empty table
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("k")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_reload_projects(self, app: AsparaTUIApp) -> None:
        """Test that Ctrl+r reloads the project list without error."""
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()


class TestRunDetailScreen:
    """Tests for RunDetailScreen."""

    @pytest.mark.asyncio
    async def test_scroll_with_j_k(self, tmp_path) -> None:
        """Test that j/k keys scroll the metrics container without error."""
        # Create a minimal project/run directory so the catalog doesn't raise
        project_dir = tmp_path / "test_project"
        project_dir.mkdir(exist_ok=True)
        (project_dir / "test_run.jsonl").touch()
        (project_dir / "test_run.meta.json").write_text("{}")

        app = AsparaTUIApp(data_dir=str(tmp_path))
        async with app.run_test() as pilot:
            screen = RunDetailScreen(project_name="test_project", run_name="test_run")
            app.push_screen(screen)
            await pilot.pause()

            # j and k should not raise errors even with no metrics
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("k")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_tab_enter_opens_metric_chart(self, tmp_path) -> None:
        """Test that Tab focuses a chart cell and Enter opens the metric chart."""
        import json

        project_dir = tmp_path / "test_project"
        project_dir.mkdir(exist_ok=True)

        # Write metrics data with one metric
        with (project_dir / "test_run.jsonl").open("w") as f:
            f.write(json.dumps({"timestamp": 1700000000000, "step": 0, "metrics": {"loss": 0.5}}) + "\n")
            f.write(json.dumps({"timestamp": 1700000001000, "step": 1, "metrics": {"loss": 0.3}}) + "\n")

        (project_dir / "test_run.meta.json").write_text("{}")

        app = AsparaTUIApp(data_dir=str(tmp_path))
        async with app.run_test() as pilot:
            screen = RunDetailScreen(project_name="test_project", run_name="test_run")
            app.push_screen(screen)
            await pilot.pause()

            # Tab to focus the first chart cell, then Enter to open it
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # Should have pushed MetricChartScreen
            from aspara.tui.screens.metric_chart import MetricChartScreen

            assert isinstance(app.screen, MetricChartScreen)


class TestMetricChartScreen:
    """Tests for MetricChartScreen."""

    @pytest.mark.asyncio
    async def test_jump_to_start_and_end(self, tmp_path) -> None:
        """Test that g/G keys jump to start/end without error."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir(exist_ok=True)
        (project_dir / "test_run.jsonl").touch()
        (project_dir / "test_run.meta.json").write_text("{}")

        app = AsparaTUIApp(data_dir=str(tmp_path))
        async with app.run_test() as pilot:
            screen = MetricChartScreen(
                project_name="test_project",
                run_name="test_run",
                metric_name="loss",
            )
            app.push_screen(screen)
            await pilot.pause()

            # g and G should not raise errors even with no data
            await pilot.press("g")
            await pilot.pause()
            await pilot.press("G")
            await pilot.pause()
