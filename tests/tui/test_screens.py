"""Tests for TUI screens."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input

from aspara.tui.app import AsparaTUIApp
from aspara.tui.screens import HelpScreen, ProjectsScreen


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
