"""Adapters exposing the file-catalog method surface over a ``LibsqlCatalog``.

The dashboard injects two distinct dependencies -- a project catalog and a run
catalog -- and calls them by the method names of the file-based
:class:`ProjectCatalog` / :class:`RunCatalog`. ``LibsqlCatalog`` is a single
object with libSQL-specific names, so these thin facades map one shared
``LibsqlCatalog`` onto those two interfaces, letting the routes stay unchanged
for libSQL-backed tenants.

A shared re-entrant lock serializes access to the underlying libSQL connection,
which is not safe for concurrent use across the worker threads the dashboard
spawns via ``asyncio.to_thread`` (e.g. the metrics endpoint loads runs in
parallel). Correctness is favored over throughput for this first wiring.

Not yet supported for libSQL tenants (kept as graceful no-ops / gaps):
- ``subscribe`` (SSE change streaming) has no watcher; the generator stays
  open until cancelled so EventSource does not reconnect in a loop.
- Artifact *bytes* for *remote* tenants (a ``database`` URL). Local libSQL
  tenants still pin files under ``base_dir``; remote tenants keep only
  artifact metadata until object storage exists. ZIP download 404s for them.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncGenerator, Mapping
from datetime import datetime
from typing import Any

import polars as pl

from aspara.models import MetricRecord, StatusRecord
from aspara.storage.artifacts.base import ArtifactStore

from .libsql_catalog import LibsqlCatalog
from .project_catalog import ProjectInfo
from .run_catalog import RunInfo


class LibsqlProjectCatalog:
    """``ProjectCatalog``-compatible facade backed by a shared ``LibsqlCatalog``."""

    def __init__(
        self,
        catalog: LibsqlCatalog,
        lock: threading.RLock | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._cat = catalog
        self._lock = lock or threading.RLock()
        self._artifacts = artifact_store

    def exists(self, name: str) -> bool:
        with self._lock:
            return self._cat.project_exists(name)

    def get_projects(self) -> list[ProjectInfo]:
        with self._lock:
            return self._cat.get_projects()

    def get_projects_with_metadata(self) -> list[tuple[ProjectInfo, dict[str, Any]]]:
        with self._lock:
            return self._cat.get_projects_with_metadata()

    def get_metadata(self, name: str) -> dict[str, Any]:
        with self._lock:
            return self._cat.get_project_metadata(name)

    def update_metadata(self, name: str, metadata: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return self._cat.update_project_metadata(name, metadata)

    def delete(self, name: str) -> None:
        with self._lock:
            # Bytes first: if the DB delete fails, the project row remains and
            # delete can be retried. DB-first would leave files that a same-name
            # recreate would mix into ZIP.
            if self._artifacts is not None:
                self._artifacts.delete_project(name)
            self._cat.delete_project(name)

    def close(self) -> None:
        """Close the shared tenant database connection."""
        self._cat.close()


class LibsqlRunCatalog:
    """``RunCatalog``-compatible facade backed by a shared ``LibsqlCatalog``."""

    def __init__(
        self,
        catalog: LibsqlCatalog,
        lock: threading.RLock | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._cat = catalog
        self._lock = lock or threading.RLock()
        self._artifacts = artifact_store

    def get_runs(self, project: str) -> list[RunInfo]:
        with self._lock:
            return self._cat.get_runs(project)

    def get(self, project: str, run: str) -> RunInfo:
        with self._lock:
            return self._cat.get_run(project, run)

    def load_metrics(self, project: str, run: str, start_time: datetime | None = None) -> pl.DataFrame:
        with self._lock:
            return self._cat.load_metrics(project, run, start_time)

    def get_metadata(self, project: str, run: str) -> dict[str, Any]:
        with self._lock:
            return self._cat.get_run_metadata(project, run)

    def update_metadata(self, project: str, run: str, metadata: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return self._cat.update_run_metadata(project, run, metadata)

    def delete(self, project: str, run: str) -> None:
        with self._lock:
            # Bytes first so a failed DB delete can be retried without mixing
            # leftover files into a same-name recreate.
            if self._artifacts is not None:
                self._artifacts.delete_run(project, run)
            self._cat.delete_run(project, run)

    def get_artifacts(self, project: str, run: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._cat.get_run_artifacts(project, run)

    def get_run_config(self, project: str, run: str) -> dict[str, Any]:
        with self._lock:
            return self._cat.get_run_config(project, run)

    async def get_artifacts_async(self, project: str, run: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.get_artifacts, project, run)

    async def get_run_config_async(self, project: str, run: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.get_run_config, project, run)

    async def get_metadata_async(self, project: str, run: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.get_metadata, project, run)

    async def subscribe(
        self,
        targets: Mapping[str, list[str] | None],
        since: datetime,
    ) -> AsyncGenerator[MetricRecord | StatusRecord, None]:
        """SSE change streaming is not supported for libSQL tenants yet.

        Yields nothing and stays open until cancelled so the SSE endpoint
        degrades to "no live updates" instead of closing (which would make
        EventSource reconnect forever). The REST metrics endpoint still serves
        the current data. The element type matches ``RunCatalog.subscribe``
        so both catalogs present an identical streaming interface.
        """
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        yield  # pragma: no cover - cancelled before any record
