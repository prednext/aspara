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
- **Deletes** remove a run's/project's rows from those tables. Local artifact
  bytes under ``base_dir`` are removed by the dashboard facades, not here.

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
from aspara.storage.metadata.libsql import (
    PROJECT_META_DDL,
    RUN_META_DDL,
    delete_project_meta,
    delete_run_meta,
    read_project_meta,
    read_run_meta,
    write_project_meta,
    write_run_meta,
)
from aspara.storage.metadata.models import validate_metadata
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


def _meta_time(value: Any) -> datetime | None:
    """Parse a metadata timestamp (UNIX ms or ISO string) to UTC, or None."""
    if value is None or isinstance(value, bool):
        return None
    with contextlib.suppress(ValueError, TypeError, OSError):
        return parse_to_datetime(value)
    return None


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
        self._base_dir = base_dir
        self._database = database
        self._auth_token = auth_token
        self._conn: Any = None
        self._open()

    def _open(self) -> None:
        """Connect and ensure schema. Close the connection if schema setup fails."""
        conn = connect_libsql(
            self._base_dir if self._database is None else None,
            database=self._database,
            auth_token=self._auth_token,
        )
        try:
            # Ensure the tables exist so discovery over a freshly provisioned
            # (empty) tenant database returns [] instead of raising "no such table".
            ensure_metrics_schema(conn)
            conn.execute(RUN_META_DDL)
            conn.execute(PROJECT_META_DDL)
            conn.commit()
        except BaseException:
            with contextlib.suppress(Exception):
                conn.close()
            raise
        self._conn = conn

    def _reopen(self) -> None:
        with contextlib.suppress(Exception):
            if self._conn is not None:
                self._conn.close()
        self._conn = None
        self._open()

    def _with_reconnect(self, fn: Any) -> Any:
        """Run ``fn`` using ``self._conn``, reconnecting once if it fails."""
        try:
            return fn()
        except Exception:
            self._reopen()
            return fn()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Run a statement, reconnecting once if the cached connection is dead."""
        return self._with_reconnect(lambda: self._conn.execute(sql, params))

    def _query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        """Execute and fetchall, reconnecting once including after a dead cursor."""
        return self._with_reconnect(lambda: self._conn.execute(sql, params).fetchall())

    def _query_one(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute and fetchone, reconnecting once including after a dead cursor."""
        return self._with_reconnect(lambda: self._conn.execute(sql, params).fetchone())

    def _execute_commit(self, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
        """Execute ``statements`` then commit, retrying the whole list after reconnect.

        ``_execute`` reconnects per statement. A multi-statement write that
        reconnects in the middle would commit only the suffix on the new
        connection and drop the prefix with the old one.
        """

        def run() -> None:
            for sql, params in statements:
                self._conn.execute(sql, params)
            self._conn.commit()

        try:
            run()
        except Exception:
            self._reopen()
            run()

    def _load_run_meta(self, project: str, run: str) -> dict[str, Any]:
        """Return the stored run metadata (defaults filled) for a run."""
        return self._with_reconnect(lambda: read_run_meta(self._conn, project, run))

    def _last_update_from_meta(self, project: str) -> datetime | None:
        """Best-effort last_update for a project that has no metric rows.

        Uses ``project_meta.updated_at`` / ``created_at``, then run_meta
        ``finish_time`` / ``start_time``. Never substitutes ``datetime.now()``.
        """
        project_meta = self._load_project_meta(project)
        for key in ("updated_at", "created_at"):
            parsed = _meta_time(project_meta.get(key))
            if parsed is not None:
                return parsed
        rows = self._query_all("SELECT data FROM run_meta WHERE project = ?", (project,))
        latest: datetime | None = None
        for (raw,) in rows:
            data: Any = None
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                data = json.loads(raw)
            if not isinstance(data, dict):
                continue
            for key in ("finish_time", "start_time"):
                parsed = _meta_time(data.get(key))
                if parsed is not None and (latest is None or parsed > latest):
                    latest = parsed
        return latest

    def _upsert_run_meta(self, project: str, run: str, meta: dict[str, Any]) -> None:
        self._with_reconnect(lambda: write_run_meta(self._conn, project, run, meta))

    def _load_project_meta(self, project: str) -> dict[str, Any]:
        """Return the stored project metadata (defaults filled) for a project."""
        return self._with_reconnect(lambda: read_project_meta(self._conn, project))

    def _upsert_project_meta(self, project: str, meta: dict[str, Any]) -> None:
        self._with_reconnect(lambda: write_project_meta(self._conn, project, meta))

    def _run_info(self, run: str, start_ts: int | None, last_ts: int | None, meta: dict[str, Any]) -> RunInfo:
        """Build a RunInfo from metric timestamps and stored metadata."""
        is_finished = bool(meta.get("is_finished", False))
        exit_code = meta.get("exit_code")
        params = meta.get("params")
        if not isinstance(params, dict):
            params = {}
        param_count = len(params)

        artifacts = meta.get("artifacts")
        if not isinstance(artifacts, list):
            artifacts = []
        tags = meta.get("tags")
        if not isinstance(tags, list):
            tags = []
        is_corrupted = not isinstance(meta.get("artifacts", []), list) or not isinstance(meta.get("tags", []), list)

        start_time = _meta_time(meta.get("start_time"))
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
            last_update=_ms_to_dt(last_ts) or _meta_time(meta.get("finish_time")) or start_time,
            param_count=param_count,
            artifact_count=len(artifacts),
            tags=[t for t in tags if isinstance(t, str)],
            is_corrupted=is_corrupted,
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
        rows = self._query_all(
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
        for name, run_count, last_ts in rows:
            projects.append(
                ProjectInfo(
                    name=name,
                    run_count=int(run_count),
                    last_update=_ms_to_dt(last_ts) or self._last_update_from_meta(name),
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

        rows = self._query_all(
            "SELECT run, MIN(start_ts) AS start_ts, MAX(last_ts) AS last_ts "
            "FROM ("
            "  SELECT run, ts AS start_ts, ts AS last_ts FROM metrics WHERE project = ? "
            "  UNION ALL "
            "  SELECT run, NULL AS start_ts, NULL AS last_ts FROM run_meta WHERE project = ?"
            ") GROUP BY run ORDER BY run",
            (project, project),
        )
        return [
            self._safe_run_info(project, run, start_ts, last_ts)
            for run, start_ts, last_ts in rows
        ]

    def _safe_run_info(self, project: str, run: str, start_ts: int | None, last_ts: int | None) -> RunInfo:
        try:
            return self._run_info(run, start_ts, last_ts, self._load_run_meta(project, run))
        except Exception as e:
            return RunInfo(
                name=run,
                param_count=0,
                is_corrupted=True,
                error_message=str(e),
                start_time=_ms_to_dt(start_ts),
                last_update=_ms_to_dt(last_ts),
            )

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

        row = self._query_one(
            "SELECT MIN(ts), MAX(ts) FROM metrics WHERE project = ? AND run = ?",
            (project, run),
        )
        start_ts, last_ts = (row[0], row[1]) if row else (None, None)
        return self._safe_run_info(project, run, start_ts, last_ts)

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

        rows = self._query_all(
            "SELECT ts, step, name, value FROM metrics WHERE project = ? AND run = ? ORDER BY ts, step",
            (project, run),
        )
        df = long_rows_to_wide(rows)

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
        artifacts = self.get_run_metadata(project, run).get("artifacts", [])
        return artifacts if isinstance(artifacts, list) else []

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
        return self._with_reconnect(lambda: delete_run_meta(self._conn, project, run))

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

        self._execute_commit([
            ("DELETE FROM metrics WHERE project = ? AND run = ?", (project, run)),
            ("DELETE FROM run_meta WHERE project = ? AND run = ?", (project, run)),
        ])

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
        return self._with_reconnect(lambda: delete_project_meta(self._conn, project))

    def delete_project(self, project: str) -> None:
        """Delete a project (all its runs' metrics and all metadata).

        Raises:
            ValueError: If the name is invalid.
            ProjectNotFoundError: If the project has no data in this database.
        """
        validate_name(project, "project name")

        if not self._project_exists(project):
            raise ProjectNotFoundError(f"Project '{project}' does not exist")

        self._execute_commit([
            ("DELETE FROM metrics WHERE project = ?", (project,)),
            ("DELETE FROM run_meta WHERE project = ?", (project,)),
            ("DELETE FROM project_meta WHERE project = ?", (project,)),
        ])

    # -- Existence helpers --------------------------------------------------

    def project_exists(self, project: str) -> bool:
        """Return True if the project has any metrics or metadata; False if the name is invalid."""
        try:
            validate_name(project, "project name")
        except ValueError:
            return False
        return self._project_exists(project)

    def _run_exists(self, project: str, run: str) -> bool:
        row = self._query_one(
            "SELECT EXISTS(SELECT 1 FROM metrics WHERE project = ? AND run = ?) "
            "OR EXISTS(SELECT 1 FROM run_meta WHERE project = ? AND run = ?)",
            (project, run, project, run),
        )
        return bool(row[0])

    def _project_exists(self, project: str) -> bool:
        row = self._query_one(
            "SELECT EXISTS(SELECT 1 FROM metrics WHERE project = ?) "
            "OR EXISTS(SELECT 1 FROM run_meta WHERE project = ?) "
            "OR EXISTS(SELECT 1 FROM project_meta WHERE project = ?)",
            (project, project, project),
        )
        return bool(row[0])

    def close(self) -> None:
        """Close the database connection."""
        conn = self._conn
        self._conn = None
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
