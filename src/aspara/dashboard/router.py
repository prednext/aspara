"""
Aspara Dashboard APIRouter aggregation.

This module aggregates all route handlers from sub-modules:
- html_routes: HTML page endpoints
- api_routes: REST API endpoints
- sse_routes: Server-Sent Events streaming endpoints

Note: experiment concept has been removed - URL structure is now /projects/{project}/runs/{run}
"""

from __future__ import annotations

from fastapi import APIRouter

# Re-export configure_data_dir for backwards compatibility
from .dependencies import configure_data_dir
from .routes import api_router, html_router, sse_router

router = APIRouter()
router.include_router(html_router)
router.include_router(api_router)
router.include_router(sse_router)

__all__ = ["router", "configure_data_dir"]
