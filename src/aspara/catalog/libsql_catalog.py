"""LibsqlCatalog - project/run discovery over a libSQL (Turso) tenant database.

Stage 2 (first slice) of the multi-tenant SaaS direction. Where ``ProjectCatalog``
and ``RunCatalog`` discover projects/runs by scanning the filesystem, this catalog
derives them from the ``metrics`` table written by :class:`LibsqlMetricsStorage`
(columns ``project``, ``run``, ``ts``, ``step``, ``name``, ``value``). One database
holds one tenant's data, so listing is a set of ``SELECT ... GROUP BY`` queries.

Scope of this slice (read-only discovery):
- ``get_projects()`` / ``get_runs(project)`` / ``load_metrics(project, run)``.

Deliberately deferred to later slices (still filesystem-only for now):
- Run/project metadata (tags, notes, params, status) and artifacts — these live in
  ``.meta.json`` / ``metadata.json`` files, not in the metrics table yet.
- SSE ``subscribe()`` (change streaming) and delete operations.

Because of that, this class is intentionally *not* a drop-in replacement for the
file-based catalogs in the dashboard yet; it is an independently testable building
block. Timestamps stored as UNIX milliseconds are surfaced as UTC ``datetime``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from aspara.exceptions import ProjectNotFoundError
from aspara.storage.metrics.libsql import connect_libsql, ensure_metrics_schema, long_rows_to_wide
from aspara.utils.validators import validate_name

from .project_catalog import ProjectInfo
from .run_catalog import RunInfo


def _ms_to_dt(ms: int | float | None) -> datetime | None:
    """Convert a UNIX-millisecond timestamp to a UTC datetime (``None`` passthrough)."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


class LibsqlCatalog:
    """Discover projects and runs from a single libSQL/Turso tenant database."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        *,
        database: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        """Open the tenant database.

        Args:
            base_dir: Base directory for a local ``{base_dir}/aspara.db`` file
                (the tenant is the directory). Ignored when ``database`` is set.
            database: Optional remote libSQL URL (``libsql://...turso.io``).
            auth_token: Optional auth token for a remote database.
        """
        self._conn: Any = connect_libsql(
            base_dir if database is None else None,
            database=database,
            auth_token=auth_token,
        )
        # Ensure the table exists so discovery over a freshly provisioned (empty)
        # tenant database returns [] instead of raising "no such table".
        ensure_metrics_schema(self._conn)

    def get_projects(self) -> list[ProjectInfo]:
        """List all projects, with run counts and last-update times.

        Returns:
            ``ProjectInfo`` list sorted by project name.
        """
        cur = self._conn.execute(
            "SELECT project, COUNT(DISTINCT run) AS run_count, MAX(ts) AS last_ts "
            "FROM metrics GROUP BY project ORDER BY project"
        )
        projects: list[ProjectInfo] = []
        for name, run_count, last_ts in cur.fetchall():
            projects.append(
                ProjectInfo(
                    name=name,
                    run_count=int(run_count),
                    last_update=_ms_to_dt(last_ts) or datetime.now(timezone.utc),
                )
            )
        return projects

    def get_runs(self, project: str) -> list[RunInfo]:
        """List all runs in a project.

        Args:
            project: Project name.

        Returns:
            ``RunInfo`` list sorted by run name. Metadata-derived fields (tags,
            params, status) use defaults in this slice; only names and the
            start/last-update times (from metric timestamps) are populated.

        Raises:
            ValueError: If the project name is invalid.
            ProjectNotFoundError: If the project has no data in this database.
        """
        validate_name(project, "project name")

        cur = self._conn.execute(
            "SELECT run, MIN(ts) AS start_ts, MAX(ts) AS last_ts "
            "FROM metrics WHERE project = ? GROUP BY run ORDER BY run",
            (project,),
        )
        rows = cur.fetchall()
        if not rows:
            raise ProjectNotFoundError(f"Project '{project}' not found")

        runs: list[RunInfo] = []
        for run, start_ts, last_ts in rows:
            runs.append(
                RunInfo(
                    name=run,
                    start_time=_ms_to_dt(start_ts),
                    last_update=_ms_to_dt(last_ts),
                    param_count=0,
                )
            )
        return runs

    def load_metrics(
        self,
        project: str,
        run: str,
        start_time: datetime | None = None,
    ) -> pl.DataFrame:
        """Load a run's metrics in wide format.

        Args:
            project: Project name.
            run: Run name.
            start_time: Optional lower bound (inclusive) on ``timestamp``.

        Returns:
            Wide-format DataFrame (``timestamp``, ``step``, ``_<metric>`` columns).
            Empty (just ``timestamp``/``step``) when the run has no rows, matching
            the file-based ``RunCatalog.load_metrics`` behavior.

        Raises:
            ValueError: If the project or run name is invalid.
        """
        validate_name(project, "project name")
        validate_name(run, "run name")

        cur = self._conn.execute(
            "SELECT ts, step, name, value FROM metrics WHERE project = ? AND run = ? ORDER BY ts, step",
            (project, run),
        )
        df = long_rows_to_wide(cur.fetchall())

        if start_time is not None and len(df) > 0:
            # The wide ``timestamp`` column is tz-naive Datetime("ms"); normalize the
            # (possibly tz-aware) cutoff to the same dtype so the comparison is valid.
            cutoff = start_time.astimezone(timezone.utc).replace(tzinfo=None)
            df = df.filter(pl.col("timestamp") >= pl.lit(cutoff, dtype=pl.Datetime("ms")))

        return df

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
