"""Aspara Tracker API application.

FastAPI application for the tracker API.
"""

from fastapi import FastAPI

from aspara.config import is_dev_mode

from .router import router

app = FastAPI(
    title="Aspara Tracker API",
    description="Web API for recording and managing run metrics",
    version="0.1.0",
    docs_url="/docs/tracker" if is_dev_mode() else None,
    redoc_url="/docs/tracker/redoc" if is_dev_mode() else None,
)

app.include_router(router)
