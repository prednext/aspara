"""
Aspara Terminal UI Dashboard

A terminal-based dashboard using Textual framework for viewing
projects, runs, and metrics.
"""

from __future__ import annotations


def run_tui(data_dir: str | None = None) -> None:
    """Run the Aspara TUI application.

    Args:
        data_dir: Data directory path. Defaults to XDG-based default.
    """
    from aspara.tui.app import AsparaTUIApp

    app = AsparaTUIApp(data_dir=data_dir)
    app.run()


__all__ = ["run_tui"]
