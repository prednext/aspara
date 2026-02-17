"""
FastAPI application for Aspara Dashboard
"""

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from aspara.config import is_dev_mode

from .router import router

logger = logging.getLogger(__name__)


# Global state for SSE connection management
class AppState:
    """Application state for managing SSE connections during shutdown."""

    def __init__(self) -> None:
        self.active_sse_connections: set[asyncio.Queue] = set()
        self.active_sse_tasks: set[asyncio.Task] = set()
        self.shutting_down = False


app_state = AppState()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking by denying framing
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS filter in browsers (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy - basic policy
        # Allows self-origin scripts/styles, inline styles for chart libraries,
        # and data: URIs for images (used by chart exports)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Allow iframe embedding when ASPARA_ALLOW_IFRAME=1 (e.g., HF Spaces)
        if os.environ.get("ASPARA_ALLOW_IFRAME") == "1":
            del response.headers["X-Frame-Options"]
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self'; "
                "frame-ancestors https://huggingface.co https://*.hf.space"
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle.

    On shutdown, signal all active SSE connections to close gracefully.
    In development mode, forcefully cancel SSE tasks for fast restart.
    """
    # Startup
    yield

    # Shutdown
    app_state.shutting_down = True

    # Signal all active SSE connections to stop
    for queue in list(app_state.active_sse_connections):
        # Queue might already be closed or event loop shutting down
        with contextlib.suppress(RuntimeError, OSError):
            await queue.put(None)  # Sentinel value to signal shutdown

    if is_dev_mode():
        # Development mode: forcefully cancel SSE tasks for fast restart
        logger.info(f"[DEV MODE] Cancelling {len(app_state.active_sse_tasks)} active SSE tasks")
        for task in list(app_state.active_sse_tasks):
            task.cancel()

        # Wait briefly for tasks to be cancelled
        if app_state.active_sse_tasks:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(*app_state.active_sse_tasks, return_exceptions=True),
                    timeout=0.1,
                )
        logger.info("[DEV MODE] SSE tasks cancelled, shutdown complete")
    else:
        # Production mode: graceful shutdown with 30 second timeout
        await asyncio.sleep(0.5)


app = FastAPI(
    title="Aspara Dashboard",
    description="Real-time metrics visualization for machine learning experiments",
    docs_url="/docs/dashboard",  # /docs/dashboard としてアクセスできるようにする
    redoc_url=None,  # ReDocは使わない
    lifespan=lifespan,
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)  # ty: ignore[invalid-argument-type]

# CORS middleware - credentials disabled for security with wildcard origins
# Note: allow_credentials=True with allow_origins=["*"] is a security vulnerability
# as it allows any site to make credentialed requests to our API
app.add_middleware(
    CORSMiddleware,  # ty: ignore[invalid-argument-type]
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Requested-With"],
)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(router)
