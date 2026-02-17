"""
Aspara main application
"""

import importlib.util
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="Aspara",
    description="A metrics tracker system for computer based experiments",
    version="0.1.0",
    docs_url=None,  # Disable default /docs
    redoc_url=None,  # Disable default /redoc
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,  # ty: ignore[invalid-argument-type]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def is_module_available(module_name: str) -> bool:
    """Check if the specified module is available

    Args:
        module_name: Module name to check

    Returns:
        bool: True if module is available, False otherwise
    """
    return importlib.util.find_spec(module_name) is not None


def should_mount_tracker() -> bool:
    """Check if tracker should be mounted based on environment variable

    Returns:
        bool: True if tracker should be mounted
    """
    env_val = os.environ.get("ASPARA_SERVE_TRACKER")
    if env_val is not None:
        return env_val == "1"
    return True  # Backward compat: mount if available


def should_mount_dashboard() -> bool:
    """Check if dashboard should be mounted based on environment variable

    Returns:
        bool: True if dashboard should be mounted
    """
    env_val = os.environ.get("ASPARA_SERVE_DASHBOARD")
    if env_val is not None:
        return env_val == "1"
    return True  # Backward compat: mount if available


@app.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request) -> HTMLResponse:
    """Root endpoint - displays links to documentation

    Args:
        request: Request object

    Returns:
        HTMLResponse: HTML containing links to documentation
    """
    tracker_available = is_module_available("aspara.tracker.main")
    dashboard_available = is_module_available("aspara.dashboard.main")

    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aspara - Documentation</title>
        <style>
            body {
                font-family: 'Inter', 'Noto Sans JP', sans-serif;
                background-color: #f5f5f5;
                color: #212121;
                line-height: 1.6;
                padding: 2rem;
                max-width: 800px;
                margin: 0 auto;
            }
            h1 {
                color: #2e639f;
                margin-bottom: 1.5rem;
            }
            .card {
                background-color: white;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
            }
            .card h2 {
                margin-top: 0;
                color: #2e639f;
            }
            a {
                color: #2e639f;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            .not-available {
                color: #9e9e9e;
                font-style: italic;
            }
        </style>
    </head>
    <body>
        <h1>Aspara Documentation</h1>

        <div class="card">
            <h2>Aspara Tracker API</h2>
    """

    if tracker_available:
        html_content += """
            <p>Web API for recording and managing experiment metrics</p>
            <p><a href="/docs/tracker">Tracker API Documentation</a> - API documentation based on OpenAPI specification</p>
            <p><a href="/tracker/redoc">Tracker API ReDoc</a> - Alternative API documentation</p>
        """
    else:
        html_content += """
            <p class="not-available">Tracker API is not installed</p>
            <p>To install: <code>uv pip install aspara[tracker]</code></p>
        """

    html_content += """
        </div>

        <div class="card">
            <h2>Aspara Dashboard</h2>
    """

    if dashboard_available:
        html_content += """
            <p>Web dashboard for visualizing experiment metrics</p>
            <p><a href="/">Open Dashboard</a> - Metrics visualization interface</p>
            <p><a href="/docs/dashboard">Dashboard API Documentation</a> - Dashboard API documentation</p>
        """
    else:
        html_content += """
            <p class="not-available">Dashboard is not installed</p>
            <p>To install: <code>uv pip install aspara[dashboard]</code></p>
        """

    html_content += """
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


if should_mount_tracker() and is_module_available("aspara.tracker.main"):
    from aspara.tracker.main import app as tracker_app

    app.mount("/tracker", tracker_app)

if should_mount_dashboard() and is_module_available("aspara.dashboard.main"):
    import importlib

    from fastapi.staticfiles import StaticFiles

    dashboard_module = importlib.import_module("aspara.dashboard.main")

    BASE_DIR = Path(__file__).parent.parent / "dashboard"
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    app.mount("", dashboard_module.app)
