#!/usr/bin/env python3
"""
Aspara CLI tool

Command line interface for starting dashboard and tracker API
"""

from __future__ import annotations

import argparse
import os
import socket
import sys

import uvicorn

from aspara.config import get_data_dir, get_storage_backend


def parse_serve_components(components: list[str]) -> tuple[bool, bool]:
    """
    Parse and validate component list for serve command

    Args:
        components: List of component names

    Returns:
        Tuple of (enable_dashboard, enable_tracker)

    Raises:
        ValueError: If invalid component name is provided
    """
    valid_components = {"dashboard", "tracker", "together"}

    # Default: dashboard only
    if not components:
        return (True, False)

    # Normalize and validate
    normalized = [c.lower() for c in components]
    for comp in normalized:
        if comp not in valid_components:
            raise ValueError(f"Invalid component: {comp}. Valid options are: dashboard, tracker, together")

    # Handle 'together' keyword
    if "together" in normalized:
        return (True, True)

    # Handle explicit component list
    enable_dashboard = "dashboard" in normalized
    enable_tracker = "tracker" in normalized

    # If both specified, enable both
    if enable_dashboard and enable_tracker:
        return (True, True)

    return (enable_dashboard, enable_tracker)


def get_default_port(enable_dashboard: bool, enable_tracker: bool) -> int:
    """
    Get default port based on enabled components

    Args:
        enable_dashboard: Whether dashboard is enabled
        enable_tracker: Whether tracker is enabled

    Returns:
        Default port number (3142 for tracker-only, 3141 otherwise)
    """
    if enable_tracker and not enable_dashboard:
        return 3142
    return 3141


def find_available_port(start_port: int = 3141, max_attempts: int = 100) -> int | None:
    """
    Find an available port number

    Args:
        start_port: Starting port number
        max_attempts: Maximum number of attempts

    Returns:
        Available port number, None if not found
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # If connection fails, that port is available
            result = sock.connect_ex(("127.0.0.1", port))
            if result != 0:
                return port
    return None


def run_dashboard(
    host: str = "127.0.0.1",
    port: int = 3141,
    with_tracker: bool = False,
    data_dir: str | None = None,
    dev: bool = False,
    project_search_mode: str = "realtime",
) -> None:
    """
    Start dashboard server

    Args:
        host: Host name
        port: Port number
        with_tracker: Whether to run integrated tracker in same process
        data_dir: Data directory for local data
        dev: Enable development mode with auto-reload
        project_search_mode: Project search mode on dashboard home (realtime or manual)
    """
    # Set env vars for component mounting
    os.environ["ASPARA_SERVE_DASHBOARD"] = "1"
    os.environ["ASPARA_SERVE_TRACKER"] = "1" if with_tracker else "0"

    if with_tracker:
        os.environ["ASPARA_WITH_TRACKER"] = "1"

    if dev:
        os.environ["ASPARA_DEV_MODE"] = "1"

    if data_dir is None:
        data_dir = str(get_data_dir())

    if project_search_mode:
        os.environ["ASPARA_PROJECT_SEARCH_MODE"] = project_search_mode

    from aspara.dashboard.router import configure_data_dir

    configure_data_dir(data_dir)

    print("Starting Aspara Dashboard server...")
    print(f"Access http://{host}:{port} in your browser!")
    print(f"Data directory: {os.path.abspath(data_dir)}")
    backend = get_storage_backend() or "jsonl (default)"
    print(f"Storage backend: {backend}")
    if dev:
        print("Development mode: auto-reload enabled")

    try:
        uvicorn.run("aspara.server:app", host=host, port=port, reload=dev)
    except ImportError:
        print("Error: Dashboard functionality is not installed!")
        print("To install: uv pip install aspara[dashboard]")
        sys.exit(1)


def run_tui(data_dir: str | None = None) -> None:
    """
    Start TUI dashboard

    Args:
        data_dir: Data directory. Defaults to XDG-based default (~/.local/share/aspara)
    """
    if data_dir is None:
        data_dir = str(get_data_dir())

    print("Starting Aspara TUI...")
    print(f"Data directory: {os.path.abspath(data_dir)}")

    try:
        from aspara.tui import run_tui as _run_tui

        _run_tui(data_dir=data_dir)
    except ImportError:
        print("TUI functionality is not installed!")
        print("To install: uv pip install aspara[tui]")
        sys.exit(1)


def run_tracker(
    host: str = "127.0.0.1",
    port: int = 3142,
    data_dir: str | None = None,
    dev: bool = False,
    storage_backend: str | None = None,
) -> None:
    """
    Start tracker API server

    Args:
        host: Host name
        port: Port number
        data_dir: Data directory. Defaults to XDG-based default (~/.local/share/aspara)
        dev: Enable development mode with auto-reload
        storage_backend: Metrics storage backend (jsonl or polars)
    """
    # Set env vars for backward compatibility
    os.environ["ASPARA_SERVE_TRACKER"] = "1"
    os.environ["ASPARA_SERVE_DASHBOARD"] = "0"

    if dev:
        os.environ["ASPARA_DEV_MODE"] = "1"

    if storage_backend is not None:
        os.environ["ASPARA_STORAGE_BACKEND"] = storage_backend

    if data_dir is None:
        data_dir = str(get_data_dir())

    print("Starting Aspara Tracker API server...")
    print(f"Endpoint: http://{host}:{port}/tracker/api/v1")
    print(f"Data directory: {os.path.abspath(data_dir)}")
    backend = get_storage_backend() or "jsonl (default)"
    print(f"Storage backend: {backend}")
    if dev:
        print("Development mode: auto-reload enabled")

    try:
        uvicorn.run("aspara.server:app", host=host, port=port, reload=dev)
    except ImportError:
        print("Error: Tracker functionality is not installed!")
        print("To install: uv pip install aspara[tracker]")
        sys.exit(1)


def run_serve(
    components: list[str],
    host: str = "127.0.0.1",
    port: int | None = None,
    data_dir: str | None = None,
    dev: bool = False,
    project_search_mode: str = "realtime",
    storage_backend: str | None = None,
) -> None:
    """
    Start Aspara server with specified components

    Args:
        components: List of components to enable (dashboard, tracker, together)
        host: Host name
        port: Port number (auto-detected if None)
        data_dir: Data directory
        dev: Enable development mode with auto-reload
        project_search_mode: Project search mode on dashboard home (realtime or manual)
        storage_backend: Metrics storage backend (jsonl or polars)
    """
    try:
        enable_dashboard, enable_tracker = parse_serve_components(components)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Set environment variables for component mounting
    os.environ["ASPARA_SERVE_DASHBOARD"] = "1" if enable_dashboard else "0"
    os.environ["ASPARA_SERVE_TRACKER"] = "1" if enable_tracker else "0"

    if dev:
        os.environ["ASPARA_DEV_MODE"] = "1"

    if storage_backend is not None:
        os.environ["ASPARA_STORAGE_BACKEND"] = storage_backend

    # Determine port
    if port is None:
        port = get_default_port(enable_dashboard, enable_tracker)

    # Configure data directory
    if data_dir is None:
        data_dir = str(get_data_dir())

    # Configure dashboard if enabled
    if enable_dashboard:
        if project_search_mode:
            os.environ["ASPARA_PROJECT_SEARCH_MODE"] = project_search_mode

        from aspara.dashboard.router import configure_data_dir

        configure_data_dir(data_dir)

    # Build component description
    if enable_dashboard and enable_tracker:
        component_desc = "Dashboard + Tracker"
    elif enable_dashboard:
        component_desc = "Dashboard"
    else:
        component_desc = "Tracker"

    print(f"Starting Aspara {component_desc} server...")
    print(f"Access http://{host}:{port} in your browser!")
    print(f"Data directory: {os.path.abspath(data_dir)}")
    backend = get_storage_backend() or "jsonl (default)"
    print(f"Storage backend: {backend}")
    if dev:
        print("Development mode: auto-reload enabled")

    try:
        uvicorn.run("aspara.server:app", host=host, port=port, reload=dev)
    except ImportError as e:
        print(f"Error: Required functionality is not installed: {e}")
        sys.exit(1)


def main() -> None:
    """
    CLI main entry point
    """
    parser = argparse.ArgumentParser(description="Aspara management tool")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    dashboard_parser = subparsers.add_parser("dashboard", help="Start dashboard server")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Host name (default: 127.0.0.1)")
    dashboard_parser.add_argument("--port", type=int, default=3141, help="Port number (default: 3141)")
    dashboard_parser.add_argument("--with-tracker", action="store_true", help="Run dashboard with integrated tracker in same process")
    dashboard_parser.add_argument("--data-dir", default=None, help="Data directory (default: XDG-based ~/.local/share/aspara)")
    dashboard_parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    dashboard_parser.add_argument(
        "--project-search-mode",
        choices=["realtime", "manual"],
        default="realtime",
        help="Project search mode on dashboard home (realtime or manual, default: realtime)",
    )

    tracker_parser = subparsers.add_parser("tracker", help="Start tracker API server")
    tracker_parser.add_argument("--host", default="127.0.0.1", help="Host name (default: 127.0.0.1)")
    tracker_parser.add_argument("--port", type=int, default=3142, help="Port number (default: 3142)")
    tracker_parser.add_argument("--data-dir", default=None, help="Data directory (default: XDG-based ~/.local/share/aspara)")
    tracker_parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    tracker_parser.add_argument(
        "--storage-backend",
        choices=["jsonl", "polars"],
        default=None,
        help="Metrics storage backend (default: jsonl or ASPARA_STORAGE_BACKEND)",
    )

    tui_parser = subparsers.add_parser("tui", help="Start terminal UI dashboard")
    tui_parser.add_argument("--data-dir", default=None, help="Data directory (default: XDG-based ~/.local/share/aspara)")

    serve_parser = subparsers.add_parser("serve", help="Start Aspara server")
    serve_parser.add_argument(
        "components",
        nargs="*",
        default=[],
        help="Components to run: dashboard, tracker, together (default: dashboard only)",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host name (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=None, help="Port number (default: 3141 for dashboard, 3142 for tracker-only)")
    serve_parser.add_argument("--data-dir", default=None, help="Data directory (default: XDG-based ~/.local/share/aspara)")
    serve_parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    serve_parser.add_argument(
        "--project-search-mode",
        choices=["realtime", "manual"],
        default="realtime",
        help="Project search mode on dashboard home (realtime or manual, default: realtime)",
    )
    serve_parser.add_argument(
        "--storage-backend",
        choices=["jsonl", "polars"],
        default=None,
        help="Metrics storage backend (default: jsonl or ASPARA_STORAGE_BACKEND)",
    )

    args = parser.parse_args()

    if args.command == "dashboard":
        run_dashboard(
            host=args.host,
            port=args.port,
            with_tracker=args.with_tracker,
            data_dir=args.data_dir,
            dev=args.dev,
            project_search_mode=args.project_search_mode,
        )
    elif args.command == "tracker":
        run_tracker(
            host=args.host,
            port=args.port,
            data_dir=args.data_dir,
            dev=args.dev,
            storage_backend=args.storage_backend,
        )
    elif args.command == "tui":
        run_tui(data_dir=args.data_dir)
    elif args.command == "serve":
        run_serve(
            components=args.components,
            host=args.host,
            port=args.port,
            data_dir=args.data_dir,
            dev=args.dev,
            project_search_mode=args.project_search_mode,
            storage_backend=args.storage_backend,
        )
    else:
        port = find_available_port(start_port=3141)
        if port is None:
            print("Error: No available port found!")
            return

        run_dashboard(port=port)


if __name__ == "__main__":
    main()
