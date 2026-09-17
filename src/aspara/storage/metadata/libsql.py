"""libSQL-backed metadata storage (multi-tenant SaaS write path).

The file-based :class:`RunMetadataStorage` / :class:`ProjectMetadataStorage`
persist a metadata dict to a ``*.meta.json`` / ``metadata.json`` file. For a
libSQL tenant the *same* dict is stored as a JSON blob in the tenant database's
``run_meta`` / ``project_meta`` tables (the shape matches, so no migration is
needed and :class:`LibsqlCatalog` reads it back unchanged).

Only the load/save/delete seams differ from the file-based classes, so these
subclasses override just those and inherit every mutation method
(``set_init``/``update_config``/``set_finish``/``set_tags``/``add_artifact``/...)
untouched.
"""

from __future__ import annotations

import contextlib
import json
import threading
from contextlib import nullcontext
from typing import Any

from aspara.storage.metrics.libsql import acquire_libsql_connection, connect_libsql
from aspara.utils.validators import validate_name

from .project import ProjectMetadataStorage
from .run import RunMetadataStorage

# Canonical DDL for the metadata tables kept alongside the metrics table in each
# tenant database. ``LibsqlCatalog`` imports these so there is a single schema
# source of truth for the read and write paths.
RUN_META_DDL = (
    "CREATE TABLE IF NOT EXISTS run_meta ("
    "  project TEXT NOT NULL,"
    "  run TEXT NOT NULL,"
    "  data TEXT NOT NULL,"
    "  PRIMARY KEY (project, run)"
    ")"
)
PROJECT_META_DDL = "CREATE TABLE IF NOT EXISTS project_meta (project TEXT PRIMARY KEY, data TEXT NOT NULL)"


def read_run_meta(conn: Any, project: str, run: str) -> dict[str, Any]:
    """Load a run_meta JSON blob, filled with ``RunMetadataStorage`` defaults."""
    cur = conn.execute(
        "SELECT data FROM run_meta WHERE project = ? AND run = ?",
        (project, run),
    )
    row = cur.fetchone()
    meta = RunMetadataStorage.default_metadata()
    if row is not None:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            loaded = json.loads(row[0])
            if isinstance(loaded, dict):
                meta.update(loaded)
    return meta


def write_run_meta(conn: Any, project: str, run: str, meta: dict[str, Any]) -> None:
    """Insert or replace a run_meta row and commit."""
    conn.execute(
        "INSERT INTO run_meta (project, run, data) VALUES (?, ?, ?) "
        "ON CONFLICT(project, run) DO UPDATE SET data = excluded.data",
        (project, run, json.dumps(meta)),
    )
    conn.commit()


def delete_run_meta(conn: Any, project: str, run: str) -> bool:
    """Delete a run_meta row. Returns True if a row existed."""
    existed = conn.execute(
        "SELECT 1 FROM run_meta WHERE project = ? AND run = ? LIMIT 1",
        (project, run),
    ).fetchone() is not None
    conn.execute("DELETE FROM run_meta WHERE project = ? AND run = ?", (project, run))
    conn.commit()
    return existed


def read_project_meta(conn: Any, project: str) -> dict[str, Any]:
    """Load a project_meta JSON blob, filled with ``ProjectMetadataStorage`` defaults."""
    cur = conn.execute("SELECT data FROM project_meta WHERE project = ?", (project,))
    row = cur.fetchone()
    meta = ProjectMetadataStorage.default_metadata()
    if row is not None:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            loaded = json.loads(row[0])
            if isinstance(loaded, dict):
                meta.update(loaded)
    return meta


def write_project_meta(conn: Any, project: str, meta: dict[str, Any]) -> None:
    """Insert or replace a project_meta row and commit."""
    conn.execute(
        "INSERT INTO project_meta (project, data) VALUES (?, ?) ON CONFLICT(project) DO UPDATE SET data = excluded.data",
        (project, json.dumps(meta)),
    )
    conn.commit()


def delete_project_meta(conn: Any, project: str) -> bool:
    """Delete a project_meta row. Returns True if a row existed."""
    existed = conn.execute(
        "SELECT 1 FROM project_meta WHERE project = ? LIMIT 1", (project,)
    ).fetchone() is not None
    conn.execute("DELETE FROM project_meta WHERE project = ?", (project,))
    conn.commit()
    return existed


class LibsqlRunMetadataStorage(RunMetadataStorage):
    """Run metadata persisted to a tenant's libSQL ``run_meta`` table.

    Same write API as :class:`RunMetadataStorage`; only the storage seam differs.
    """

    def __init__(
        self,
        base_dir: str | None,
        project_name: str,
        run_name: str,
        *,
        database: str | None = None,
        auth_token: str | None = None,
        reuse_connection: bool = False,
    ) -> None:
        """Open the tenant database and load this run's metadata.

        Args:
            base_dir: Base directory for a local ``{base_dir}/aspara.db`` file.
                Ignored when ``database`` is set.
            project_name: Project name (validated).
            run_name: Run name (validated).
            database: Optional remote libSQL URL.
            auth_token: Optional auth token for a remote database.
            reuse_connection: When True, borrow a pooled tenant connection.
        """
        validate_name(project_name, "project name")
        validate_name(run_name, "run name")

        self.project_name = project_name
        self.run_name = run_name
        self._lease = None

        if reuse_connection:
            lease = acquire_libsql_connection(
                base_dir if database is None else None,
                database=database,
                auth_token=auth_token,
            )
            try:
                with lease.lock:
                    lease.conn.execute(RUN_META_DDL)
                    lease.conn.commit()
                    self._conn = lease.conn
                    self._lease = lease
                    self._metadata: dict[str, Any] = self.default_metadata()
                    self._load()
            except BaseException:
                lease.release()
                raise
            return

        conn = connect_libsql(
            base_dir if database is None else None,
            database=database,
            auth_token=auth_token,
        )
        try:
            conn.execute(RUN_META_DDL)
            conn.commit()
            self._conn = conn
            self._metadata = self.default_metadata()
            self._load()
        except BaseException:
            with contextlib.suppress(Exception):
                conn.close()
            raise

    def _conn_lock(self) -> threading.RLock | nullcontext[None]:
        return self._lease.lock if self._lease is not None else nullcontext()

    def _load(self) -> None:
        with self._conn_lock():
            self._metadata = read_run_meta(self._conn, self.project_name, self.run_name)

    def _save(self) -> None:
        with self._conn_lock():
            write_run_meta(self._conn, self.project_name, self.run_name, self._metadata)

    def exists(self) -> bool:
        """Return True if this run has a metadata row (analogous to the file existing)."""
        with self._conn_lock():
            cur = self._conn.execute(
                "SELECT 1 FROM run_meta WHERE project = ? AND run = ? LIMIT 1",
                (self.project_name, self.run_name),
            )
            return cur.fetchone() is not None

    def delete_metadata(self) -> bool:
        with self._conn_lock():
            existed = delete_run_meta(self._conn, self.project_name, self.run_name)
        self._metadata = self.default_metadata()
        return existed

    def close(self) -> None:
        """Close the database connection, or return a pooled one to the cache."""
        if self._lease is not None:
            self._lease.release()
            self._lease = None
            return
        self._conn.close()


class LibsqlProjectMetadataStorage(ProjectMetadataStorage):
    """Project metadata persisted to a tenant's libSQL ``project_meta`` table."""

    def __init__(
        self,
        base_dir: str | None,
        project_name: str,
        *,
        database: str | None = None,
        auth_token: str | None = None,
        reuse_connection: bool = False,
    ) -> None:
        """Open the tenant database and load this project's metadata."""
        validate_name(project_name, "project name")

        self.project_name = project_name
        self._lease = None

        if reuse_connection:
            lease = acquire_libsql_connection(
                base_dir if database is None else None,
                database=database,
                auth_token=auth_token,
            )
            try:
                with lease.lock:
                    lease.conn.execute(PROJECT_META_DDL)
                    lease.conn.commit()
                    self._conn = lease.conn
                    self._lease = lease
                    self._metadata: dict[str, Any] = self.default_metadata()
                    self._load()
            except BaseException:
                lease.release()
                raise
            return

        conn = connect_libsql(
            base_dir if database is None else None,
            database=database,
            auth_token=auth_token,
        )
        try:
            conn.execute(PROJECT_META_DDL)
            conn.commit()
            self._conn = conn
            self._metadata = self.default_metadata()
            self._load()
        except BaseException:
            with contextlib.suppress(Exception):
                conn.close()
            raise

    def _conn_lock(self) -> threading.RLock | nullcontext[None]:
        return self._lease.lock if self._lease is not None else nullcontext()

    def _load(self) -> None:
        with self._conn_lock():
            self._metadata = read_project_meta(self._conn, self.project_name)

    def _save(self) -> None:
        with self._conn_lock():
            write_project_meta(self._conn, self.project_name, self._metadata)

    def exists(self) -> bool:
        """Return True if this project has a metadata row."""
        with self._conn_lock():
            cur = self._conn.execute("SELECT 1 FROM project_meta WHERE project = ? LIMIT 1", (self.project_name,))
            return cur.fetchone() is not None

    def delete_metadata(self) -> bool:
        with self._conn_lock():
            existed = delete_project_meta(self._conn, self.project_name)
        self._metadata = self.default_metadata()
        return existed

    def close(self) -> None:
        """Close the database connection, or return a pooled one to the cache."""
        if self._lease is not None:
            self._lease.release()
            self._lease = None
            return
        self._conn.close()
