"""LibsqlMetricsStorage - libSQL/Turso-backed metrics storage (multi-tenant SaaS path).

This backend stores metrics in a libSQL database (SQLite-compatible; the engine behind
Turso). It is the first vertical slice of the multi-tenant SaaS direction: a single
database holds one tenant's data, with ``project`` and ``run`` kept as columns
(long-format ``metrics`` table) so that provisioning stays "one database per tenant"
while the existing project/run model is preserved.

Two connection modes:
- **Local file** (default): a ``aspara.db`` file under ``base_dir``. Here the *tenant*
  is the ``base_dir`` — different tenants get different directories/databases. Useful
  for tests and self-host.
- **Remote** (Turso): when a database URL + auth token are provided, connect to the
  remote database. Writes are remote-only for now (see spikes/turso_libsql/FINDINGS.md).

``load()`` returns the same wide format as the jsonl/polars backends (columns
``timestamp`` [Datetime], ``step`` [Int64], and ``_<metric>`` [Float64]) so it is a
drop-in replacement.

The ``libsql`` package is imported lazily by the storage factory, so it is only required
when this backend is actually selected (``ASPARA_STORAGE_BACKEND=libsql``).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import polars as pl

from aspara.exceptions import RunNotFoundError

from .base import MetricsStorage


def _to_epoch_ms(value: Any) -> int:
    """Normalize a timestamp to UNIX milliseconds.

    Accepts what the various write paths produce: an ``int``/``float`` already in
    milliseconds, a ``datetime``, or an ISO-8601 string (as emitted by
    ``MetricRecord.model_dump(mode="json")``). Naive datetimes are treated as UTC.
    """
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dt.datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)
        return int(moment.timestamp() * 1000)
    if isinstance(value, str):
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return int(parsed.timestamp() * 1000)
    return int(value)

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS metrics ("
    "  project TEXT NOT NULL,"
    "  run TEXT NOT NULL,"
    "  ts INTEGER NOT NULL,"
    "  step INTEGER NOT NULL,"
    "  name TEXT NOT NULL,"
    "  value REAL NOT NULL"
    ")"
)
_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS idx_metrics_pr_name_step ON metrics(project, run, name, step)"

_LONG_SCHEMA = {
    "timestamp": pl.Int64,
    "step": pl.Int64,
    "metric_name": pl.Utf8,
    "metric_value": pl.Float64,
}
_EMPTY_WIDE_SCHEMA = {"timestamp": pl.Datetime("ms"), "step": pl.Int64}


def connect_libsql(
    base_dir: str | Path | None = None,
    *,
    database: str | None = None,
    auth_token: str | None = None,
) -> Any:
    """Connect to a libSQL database (local file or remote Turso).

    Exactly one of ``base_dir`` (local ``{base_dir}/aspara.db``) or ``database``
    (a ``libsql://`` URL) selects the target. The ``libsql`` package is imported
    lazily so it is only required when this backend is actually used.

    Args:
        base_dir: Base directory for the local ``aspara.db`` file (per-tenant).
        database: Remote libSQL database URL. Takes precedence over ``base_dir``.
        auth_token: Auth token for a remote database.

    Returns:
        An open libSQL connection.
    """
    try:
        import libsql  # lazy: only needed for this backend
    except ImportError as e:  # pragma: no cover - depends on optional install
        raise ImportError(
            "The 'libsql' backend requires the 'libsql' package, which is not installed. "
            "Install it (e.g. `uv add libsql`) or choose another ASPARA_STORAGE_BACKEND."
        ) from e

    # ``libsql`` is a native extension without type stubs, so the checker can't see ``connect``.
    if database is not None:
        return libsql.connect(database, auth_token=auth_token or "")  # ty: ignore[unresolved-attribute]
    if base_dir is None:
        raise ValueError("connect_libsql requires either base_dir (local) or database (remote)")
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    return libsql.connect(str(base / "aspara.db"))  # ty: ignore[unresolved-attribute]


def ensure_metrics_schema(conn: Any) -> None:
    """Create the ``metrics`` table and index if they do not already exist."""
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_INDEX)
    conn.commit()


def long_rows_to_wide(
    rows: list[tuple[int, int, str, float]],
    metric_names: list[str] | None = None,
) -> pl.DataFrame:
    """Pivot long-format ``(ts, step, name, value)`` rows into the wide format.

    The result matches the jsonl/polars backends: columns ``timestamp``
    (Datetime("ms")), ``step`` (Int64), and ``_<metric>`` (Float64) per metric.
    An empty result (no rows, or none matching ``metric_names``) returns just the
    ``timestamp``/``step`` columns.
    """
    df_long = pl.DataFrame(rows, schema=_LONG_SCHEMA, orient="row")

    if metric_names is not None:
        df_long = df_long.filter(pl.col("metric_name").is_in(metric_names))

    if df_long.is_empty():
        return pl.DataFrame(schema=_EMPTY_WIDE_SCHEMA)

    df_long = df_long.with_columns(
        pl.col("timestamp").cast(pl.Datetime("ms")),
        pl.concat_str([pl.lit("_"), pl.col("metric_name")]).alias("metric_name"),
    )

    return df_long.pivot(
        values="metric_value",
        index=["timestamp", "step"],
        on="metric_name",
        aggregate_function="first",
    ).sort(["timestamp", "step"])


class LibsqlMetricsStorage(MetricsStorage):
    """MetricsStorage backed by a libSQL/Turso database (one database per tenant)."""

    def __init__(
        self,
        base_dir: str | Path,
        project_name: str,
        run_name: str,
        *,
        database: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        """Initialize libSQL storage.

        Args:
            base_dir: Base directory; when ``database`` is None, the local database file
                ``{base_dir}/aspara.db`` is used (the tenant is the base_dir).
            project_name: Project name (stored as a column).
            run_name: Run name (stored as a column).
            database: Optional libSQL database URL (e.g. ``libsql://...turso.io``).
                When set, connects remotely instead of using a local file.
            auth_token: Optional auth token for a remote database.
        """
        self.project_name = project_name
        self.run_name = run_name

        # ``self._conn`` is typed Any because ``libsql`` ships no type stubs.
        self._conn: Any = connect_libsql(base_dir if database is None else None, database=database, auth_token=auth_token)
        ensure_metrics_schema(self._conn)

    def save(self, metrics_data: dict[str, Any]) -> str:
        """Insert one step's metrics for this project/run and commit.

        Non-numeric metric values are skipped (metrics must be numeric).

        Args:
            metrics_data: Dict with ``timestamp`` (UNIX ms), ``step``, and ``metrics``.

        Returns:
            str: Empty string.
        """
        ts = _to_epoch_ms(metrics_data.get("timestamp", 0))
        raw_step = metrics_data.get("step")
        step = 0 if raw_step is None else int(raw_step)
        metrics: dict[str, Any] = metrics_data.get("metrics", {})

        rows: list[tuple[str, str, int, int, str, float]] = []
        for name, value in metrics.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Metric '{name}' must be numeric, got {type(value).__name__}") from e
            rows.append((self.project_name, self.run_name, ts, step, name, numeric))

        if rows:
            self._conn.executemany(
                "INSERT INTO metrics (project, run, ts, step, name, value) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()
        return ""

    def load(
        self,
        metric_names: list[str] | None = None,
    ) -> pl.DataFrame:
        """Load this run's metrics in wide format.

        Args:
            metric_names: Optional list of metric names to filter by.

        Returns:
            Polars DataFrame in wide format with columns:
            - timestamp: Datetime("ms")
            - step: Int64
            - _<metric_name>: Float64 for each metric (underscore-prefixed)

        Raises:
            RunNotFoundError: If the run has no rows in this database.
        """
        cur = self._conn.execute(
            "SELECT ts, step, name, value FROM metrics WHERE project = ? AND run = ? ORDER BY ts, step",
            (self.project_name, self.run_name),
        )
        rows = cur.fetchall()
        if not rows:
            raise RunNotFoundError(f"Run '{self.run_name}' not found in project '{self.project_name}'")

        return long_rows_to_wide(rows, metric_names)

    def finish(self) -> None:
        """Commit any pending writes."""
        self._conn.commit()

    def close(self) -> None:
        """Commit and close the database connection."""
        try:
            self._conn.commit()
        finally:
            self._conn.close()
