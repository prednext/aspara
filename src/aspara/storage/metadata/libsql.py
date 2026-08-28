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
from typing import Any

from aspara.storage.metrics.libsql import connect_libsql
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
    ) -> None:
        """Open the tenant database and load this run's metadata.

        Args:
            base_dir: Base directory for a local ``{base_dir}/aspara.db`` file.
                Ignored when ``database`` is set.
            project_name: Project name (validated).
            run_name: Run name (validated).
            database: Optional remote libSQL URL.
            auth_token: Optional auth token for a remote database.
        """
        validate_name(project_name, "project name")
        validate_name(run_name, "run name")

        self.project_name = project_name
        self.run_name = run_name

        self._conn: Any = connect_libsql(
            base_dir if database is None else None,
            database=database,
            auth_token=auth_token,
        )
        self._conn.execute(RUN_META_DDL)
        self._conn.commit()

        self._metadata: dict[str, Any] = self.default_metadata()
        self._load()

    def _load(self) -> None:
        cur = self._conn.execute(
            "SELECT data FROM run_meta WHERE project = ? AND run = ?",
            (self.project_name, self.run_name),
        )
        row = cur.fetchone()
        if row is not None:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                self._metadata.update(json.loads(row[0]))

    def _save(self) -> None:
        self._conn.execute(
            "INSERT INTO run_meta (project, run, data) VALUES (?, ?, ?) "
            "ON CONFLICT(project, run) DO UPDATE SET data = excluded.data",
            (self.project_name, self.run_name, json.dumps(self._metadata)),
        )
        self._conn.commit()

    def exists(self) -> bool:
        """Return True if this run has a metadata row (analogous to the file existing)."""
        cur = self._conn.execute(
            "SELECT 1 FROM run_meta WHERE project = ? AND run = ? LIMIT 1",
            (self.project_name, self.run_name),
        )
        return cur.fetchone() is not None

    def delete_metadata(self) -> bool:
        existed = self.exists()
        self._conn.execute(
            "DELETE FROM run_meta WHERE project = ? AND run = ?",
            (self.project_name, self.run_name),
        )
        self._conn.commit()
        self._metadata = self.default_metadata()
        return existed

    def close(self) -> None:
        """Close the database connection."""
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
    ) -> None:
        """Open the tenant database and load this project's metadata."""
        validate_name(project_name, "project name")

        self.project_name = project_name

        self._conn: Any = connect_libsql(
            base_dir if database is None else None,
            database=database,
            auth_token=auth_token,
        )
        self._conn.execute(PROJECT_META_DDL)
        self._conn.commit()

        self._metadata: dict[str, Any] = self.default_metadata()
        self._load()

    def _load(self) -> None:
        cur = self._conn.execute("SELECT data FROM project_meta WHERE project = ?", (self.project_name,))
        row = cur.fetchone()
        if row is not None:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                self._metadata = self._merge_loaded(json.loads(row[0]))

    def _save(self) -> None:
        self._conn.execute(
            "INSERT INTO project_meta (project, data) VALUES (?, ?) ON CONFLICT(project) DO UPDATE SET data = excluded.data",
            (self.project_name, json.dumps(self._metadata)),
        )
        self._conn.commit()

    def exists(self) -> bool:
        """Return True if this project has a metadata row."""
        cur = self._conn.execute("SELECT 1 FROM project_meta WHERE project = ? LIMIT 1", (self.project_name,))
        return cur.fetchone() is not None

    def delete_metadata(self) -> bool:
        existed = self.exists()
        self._conn.execute("DELETE FROM project_meta WHERE project = ?", (self.project_name,))
        self._conn.commit()
        self._metadata = self.default_metadata()
        return existed

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
