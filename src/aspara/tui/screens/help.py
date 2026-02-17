"""
Help Screen

Displays keybinding help and usage information.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[bold]Aspara TUI - Keyboard Shortcuts[/bold]

[bold underline]Global[/bold underline]
  [cyan]q[/]           Quit application
  [cyan]?[/]           Show this help
  [cyan]Backspace[/]   Go back to previous screen
  [cyan]Esc[/]         Go back / Close modal

[bold underline]Navigation (vim-style)[/bold underline]
  [cyan]j[/] / [cyan]↓[/]       Move down
  [cyan]k[/] / [cyan]↑[/]       Move up
  [cyan]Enter[/]       Select / Confirm
  [cyan]/[/]           Focus search input
  [cyan]s[/]           Toggle sort order

[bold underline]Chart View[/bold underline]
  [cyan]h[/] / [cyan]←[/]       Pan left
  [cyan]l[/] / [cyan]→[/]       Pan right
  [cyan]+[/] / [cyan]=[/]       Zoom in
  [cyan]-[/]           Zoom out
  [cyan]r[/]           Reset view
  [cyan]w[/]           Toggle live watch mode

[bold underline]Status Icons[/bold underline]
  [yellow]●[/]           Running (WIP)
  [green]✓[/]           Completed
  [red]✗[/]           Failed
  [yellow]?[/]           Maybe Failed

Press [cyan]Esc[/] or [cyan]?[/] to close this help.
"""


class HelpScreen(ModalScreen[None]):
    """Modal screen displaying help information."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("question_mark", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    HelpScreen Static {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the help screen."""
        yield Container(
            VerticalScroll(
                Static(HELP_TEXT),
            ),
        )

    async def action_dismiss(self, result: None = None) -> None:
        """Dismiss the help screen."""
        self.dismiss(result)
