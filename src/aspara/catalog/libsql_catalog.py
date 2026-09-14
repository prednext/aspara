"""LibsqlCatalog - project/run catalog over a libSQL (Turso) tenant database.

Stage 2 of the multi-tenant SaaS direction. Where ``ProjectCatalog`` and
``RunCatalog`` discover projects/runs by scanning the filesystem, this catalog
keeps everything in one tenant database:

- **Discovery** unions the ``metrics`` table with ``run_meta`` / ``project_meta``,
  so a ``create_run`` that has not yet logged a metric still appears in project
  and run listings. Metric timestamps still come from ``metrics`` when present.
- **Metadata** (tags, notes, params, status, artifacts, timestamps) lives in
  ``run_meta`` / ``project_meta`` tables as JSON blobs whose shape matches the
  file-based ``*.meta.json`` / ``metadata.json`` payloads, so no migration is
  needed as fields evolve.
- **Deletes** remove a run's/project's rows from those tables.

Timestamps stored as UNIX milliseconds are surfaced as UTC ``datetime``.

Still deferred (these remain filesystem-bound and block a full dashboard swap):
- SSE ``subscribe()`` change streaming (needs a watcher/notification source).
- Artifact *file* bytes and ZIP download (metadata is here; blobs are not).
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from aspara.exceptions import ProjectNotFoundError, RunNotFoundError
from aspara.models import RunStatus
from aspara.storage.metadata.libsql import PROJECT_META_DDL, RUN_META_DDL
from aspara.storage.metadata.models import validate_metadata
from aspara.storage.metadata.project import ProjectMetadataStorage
from aspara.storage.metadata.run import RunMetadataStorage
from aspara.storage.metrics.libsql import connect_libsql, ensure_metrics_schema, long_rows_to_wide
from aspara.utils.timestamp import parse_to_datetime
from aspara.utils.validators import validate_name

from .project_catalog import ProjectInfo
from .run_catalog import RunInfo, _infer_stale_status

# Metadata tables (``run_meta`` / ``project_meta``) live alongside the metrics table
# in the same tenant database. Each row stores the run/project metadata dict as a JSON
# blob (the same shape the file-based ``*.meta.json`` / ``metadata.json`` files use).
# The DDL is owned by ``aspara.storage.metadata.libsql`` so the read (this catalog) and
# write (LibsqlRunMetadataStorage/LibsqlProjectMetadataStorage) paths share one schema.


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
        # Ensure the tables exist so discovery over a freshly provisioned (empty)
        # tenant database returns [] instead of raising "no such table".
        ensure_metrics_schema(self._conn)
        self._conn.execute(RUN_META_DDL)
        self._conn.execute(PROJECT_META_DDL)
        self._conn.commit()

    def _load_run_meta(self, project: str, run: str) -> dict[str, Any]:
        """Return the stored run metadata (defaults filled) for a run."""
        cur = self._conn.execute(
            "SELECT data FROM run_meta WHERE project = ? AND run = ?",
            (project, run),
        )
        row = cur.fetchone()
        meta = RunMetadataStorage.default_metadata()
        if row is not None:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                meta.update(json.loads(row[0]))
        return meta

    def _upsert_run_meta(self, project: str, run: str, meta: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO run_meta (project, run, data) VALUES (?, ?, ?) "
            "ON CONFLICT(project, run) DO UPDATE SET data = excluded.data",
            (project, run, json.dumps(meta)),
        )
        self._conn.commit()

    def _load_project_meta(self, project: str) -> dict[str, Any]:
        """Return the stored project metadata (defaults filled) for a project."""
        cur = self._conn.execute("SELECT data FROM project_meta WHERE project = ?", (project,))
        row = cur.fetchone()
        meta = ProjectMetadataStorage.default_metadata()
        if row is not None:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                meta.update(json.loads(row[0]))
        return meta

    def _upsert_project_meta(self, project: str, meta: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO project_meta (project, data) VALUES (?, ?) ON CONFLICT(project) DO UPDATE SET data = excluded.data",
            (project, json.dumps(meta)),
        )
        self._conn.commit()

    def _run_info(self, run: str, start_ts: int | None, last_ts: int | None, meta: dict[str, Any]) -> RunInfo:
        """Build a RunInfo from metric timestamps and stored metadata."""
        is_finished = bool(meta.get("is_finished", False))
        exit_code = meta.get("exit_code")
        params = meta.get("params", {})
        param_count = len(params) if isinstance(params, dict) else 0

        start_time = None
        if meta.get("start_time") is not None:
            with contextlib.suppress(ValueError):
                start_time = parse_to_datetime(meta["start_time"])
        if start_time is None:
            start_time = _ms_to_dt(start_ts)

        try:
            status = RunStatus(meta.get("status", RunStatus.WIP.value))
        except ValueError:
            status = RunStatus.from_is_finished_and_exit_code(is_finished, exit_code)
        status = _infer_stale_status(status, start_time, is_finished)

        return RunInfo(
            name=run,
            run_id=meta.get("run_id"),
            start_time=start_time,
            last_update=_ms_to_dt(last_ts),
            param_count=param_count,
            artifact_count=len(meta.get("artifacts", [])),
            tags=list(meta.get("tags", [])),
            is_finished=is_finished,
            exit_code=exit_code,
            status=status,
        )

    def get_projects(self) -> list[ProjectInfo]:
        """List all projects, with run counts and last-update times.

        A project is listed if it has metric rows, run metadata, or project
        metadata. ``run_count`` is the number of distinct runs across metrics
        and ``run_meta`` (a metadata-only init counts as a run).

        Returns:
            ``ProjectInfo`` list sorted by project name.
        """
        cur = self._conn.execute(
            "SELECT project, COUNT(DISTINCT run) AS run_count, MAX(last_ts) AS last_ts "
            "FROM ("
            "  SELECT project, run, ts AS last_ts FROM metrics "
            "  UNION ALL "
            "  SELECT project, run, NULL AS last_ts FROM run_meta "
            "  UNION ALL "
            "  SELECT project, NULL AS run, NULL AS last_ts FROM project_meta"
            ") GROUP BY project ORDER BY project"
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

    def get_projects_with_metadata(self) -> list[tuple[ProjectInfo, dict[str, Any]]]:
        """List all projects paired with their metadata (notes, tags, timestamps)."""
        return [(project, self._load_project_meta(project.name)) for project in self.get_projects()]

    def get_runs(self, project: str) -> list[RunInfo]:
        """List all runs in a project, enriched with stored run metadata.

        Args:
            project: Project name.

        Returns:
            ``RunInfo`` list sorted by run name. Timestamps come from metric rows
            when present; tags, params, status, and finish state come from
            ``run_meta``. A metadata-only run (no metric rows yet) is included.

        Raises:
            ValueError: If the project name is invalid.
            ProjectNotFoundError: If the project has no data in this database.
        """
        validate_name(project, "project name")
        if not self._project_exists(project):
            raise ProjectNotFoundError(f"Project '{project}' not found")

        cur = self._conn.execute(
            "SELECT run, MIN(start_ts) AS start_ts, MAX(last_ts) AS last_ts "
            "FROM ("
            "  SELECT run, ts AS start_ts, ts AS last_ts FROM metrics WHERE project = ? "
            "  UNION ALL "
            "  SELECT run, NULL AS start_ts, NULL AS last_ts FROM run_meta WHERE project = ?"
            ") GROUP BY run ORDER BY run",
            (project, project),
        )
        return [
            self._run_info(run, start_ts, last_ts, self._load_run_meta(project, run))
            for run, start_ts, last_ts in cur.fetchall()
        ]

    def get_run(self, project: str, run: str) -> RunInfo:
        """Return a single run's info, enriched with stored metadata.

        Raises:
            ValueError: If names are invalid.
            RunNotFoundError: If the run has neither metrics nor metadata.
        """
        validate_name(project, "project name")
        validate_name(run, "run name")

        if not self._run_exists(project, run):
            raise RunNotFoundError(f"Run '{run}' not found in project '{project}'")

        row = self._conn.execute(
            "SELECT MIN(ts), MAX(ts) FROM metrics WHERE project = ? AND run = ?",
            (project, run),
        ).fetchone()
        start_ts, last_ts = (row[0], row[1]) if row else (None, None)
        return self._run_info(run, start_ts, last_ts, self._load_run_meta(project, run))

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

    # -- Run metadata -------------------------------------------------------

    def get_run_metadata(self, project: str, run: str) -> dict[str, Any]:
        """Return a run's full metadata dict (defaults filled when absent)."""
        validate_name(project, "project name")
        validate_name(run, "run name")
        return self._load_run_meta(project, run)

    # The dashboard reads run config (params/status/etc.) via the whole meta dict.
    get_run_config = get_run_metadata

    def get_run_artifacts(self, project: str, run: str) -> list[dict[str, Any]]:
        """Return a run's artifact list from its metadata."""
        return list(self.get_run_metadata(project, run).get("artifacts", []))

    def update_run_metadata(self, project: str, run: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Update a run's ``notes``/``tags`` and return the full metadata dict.

        Raises:
            ValueError: If names are invalid or notes/tags exceed limits.
        """
        validate_name(project, "project name")
        validate_name(run, "run name")
        validate_metadata(metadata)

        meta = self._load_run_meta(project, run)
        if "notes" in metadata:
            meta["notes"] = metadata["notes"]
        if "tags" in metadata:
            meta["tags"] = metadata["tags"]
        self._upsert_run_meta(project, run, meta)
        return meta

    def delete_run_metadata(self, project: str, run: str) -> bool:
        """Delete a run's metadata row. Returns True if a row existed."""
        validate_name(project, "project name")
        validate_name(run, "run name")
        existed = self._conn.execute(
            "SELECT 1 FROM run_meta WHERE project = ? AND run = ? LIMIT 1", (project, run)
        ).fetchone() is not None
        self._conn.execute("DELETE FROM run_meta WHERE project = ? AND run = ?", (project, run))
        self._conn.commit()
        return existed

    def delete_run(self, project: str, run: str) -> None:
        """Delete a run's metrics and metadata from the tenant database.

        Raises:
            ValueError: If names are invalid.
            RunNotFoundError: If the run has neither metrics nor metadata.
        """
        validate_name(project, "project name")
        validate_name(run, "run name")

        if not self._run_exists(project, run):
            raise RunNotFoundError(f"Run '{run}' does not exist in project '{project}'")

        self._conn.execute("DELETE FROM metrics WHERE project = ? AND run = ?", (project, run))
        self._conn.execute("DELETE FROM run_meta WHERE project = ? AND run = ?", (project, run))
        self._conn.commit()

    # -- Project metadata ---------------------------------------------------

    def get_project_metadata(self, project: str) -> dict[str, Any]:
        """Return a project's metadata dict (defaults filled when absent)."""
        validate_name(project, "project name")
        return self._load_project_meta(project)

    def update_project_metadata(self, project: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Update a project's ``notes``/``tags`` (timestamps managed automatically).

        Raises:
            ValueError: If the name is invalid or notes/tags exceed limits.
        """
        validate_name(project, "project name")
        validate_metadata(metadata)

        meta = self._load_project_meta(project)
        now = datetime.now(timezone.utc).isoformat()
        if meta.get("created_at") is None:
            meta["created_at"] = now
        meta["updated_at"] = now
        if "notes" in metadata:
            meta["notes"] = metadata["notes"]
        if "tags" in metadata:
            meta["tags"] = metadata["tags"]
        self._upsert_project_meta(project, meta)
        return meta

    def delete_project_metadata(self, project: str) -> bool:
        """Delete a project's metadata row. Returns True if a row existed."""
        validate_name(project, "project name")
        existed = self._conn.execute(
            "SELECT 1 FROM project_meta WHERE project = ? LIMIT 1", (project,)
        ).fetchone() is not None
        self._conn.execute("DELETE FROM project_meta WHERE project = ?", (project,))
        self._conn.commit()
        return existed

    def delete_project(self, project: str) -> None:
        """Delete a project (all its runs' metrics and all metadata).

        Raises:
            ValueError: If the name is invalid.
            ProjectNotFoundError: If the project has no data in this database.
        """
        validate_name(project, "project name")

        if not self._project_exists(project):
            raise ProjectNotFoundError(f"Project '{project}' does not exist")

        self._conn.execute("DELETE FROM metrics WHERE project = ?", (project,))
        self._conn.execute("DELETE FROM run_meta WHERE project = ?", (project,))
        self._conn.execute("DELETE FROM project_meta WHERE project = ?", (project,))
        self._conn.commit()

    # -- Existence helpers --------------------------------------------------

    def project_exists(self, project: str) -> bool:
        """Return True if the project has any metrics or metadata; False if the name is invalid."""
        try:
            validate_name(project, "project name")
        except ValueError:
            return False
        return self._project_exists(project)

    def _run_exists(self, project: str, run: str) -> bool:
        cur = self._conn.execute(
            "SELECT EXISTS(SELECT 1 FROM metrics WHERE project = ? AND run = ?) "
            "OR EXISTS(SELECT 1 FROM run_meta WHERE project = ? AND run = ?)",
            (project, run, project, run),
        )
        return bool(cur.fetchone()[0])

    def _project_exists(self, project: str) -> bool:
        cur = self._conn.execute(
            "SELECT EXISTS(SELECT 1 FROM metrics WHERE project = ?) "
            "OR EXISTS(SELECT 1 FROM run_meta WHERE project = ?) "
            "OR EXISTS(SELECT 1 FROM project_meta WHERE project = ?)",
            (project, project, project),
        )
        return bool(cur.fetchone()[0])

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
