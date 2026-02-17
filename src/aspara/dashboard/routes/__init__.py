"""
Aspara Dashboard routes.

This package contains route handlers organized by type:
- html_routes: HTML page endpoints
- api_routes: REST API endpoints
- sse_routes: Server-Sent Events streaming endpoints
"""

from .api_routes import router as api_router
from .html_routes import router as html_router
from .sse_routes import router as sse_router

__all__ = ["html_router", "api_router", "sse_router"]
