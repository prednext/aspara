"""Spike: a libSQL-backed implementation of aspara's MetricsStorage interface.

This is a proof-of-concept for the multi-tenant SaaS direction, NOT production code.
It validates that libSQL (SQLite-compatible, the engine behind Turso) can slot into
the existing ``MetricsStorage`` abstraction with a "one database file per tenant" model.

Design:
- Each instance is bound to a single tenant/project database file (``db_path``).
- Metrics are stored long-format: (ts, step, name, value).
- ``save()`` buffers inserts; ``flush()``/``finish()``/``close()`` commit them.

Local files here mirror what Turso Cloud would host as per-tenant databases, so the
numbers we measure locally (write speed, on-disk size, open latency) are a first-order
proxy for the managed cost/latency story.
"""

from __future__ import annotations

import os
from typing import Any

import libsql  # type: ignore[import-not-found]
import polars as pl

from aspara.storage.metrics.base import MetricsStorage

_SCHEMA = ["timestamp", "step", "metric", "value"]


class LibsqlMetricsStorage(MetricsStorage):
    """MetricsStorage backed by a single libSQL database file (one per tenant)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = libsql.connect(db_path)
        self._conn.execute("CREATE TABLE IF NOT EXISTS metrics (  ts INTEGER NOT NULL,  step INTEGER NOT NULL,  name TEXT NOT NULL,  value REAL NOT NULL)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name_step ON metrics(name, step)")
        self._conn.commit()

    def save(self, metrics_data: dict[str, Any]) -> str:
        """Insert one step's metrics. Not committed until flush()/finish()/close()."""
        ts = int(metrics_data.get("timestamp", 0))
        step = int(metrics_data.get("step", 0))
        metrics: dict[str, Any] = metrics_data.get("metrics", {})
        rows = [(ts, step, name, float(value)) for name, value in metrics.items()]
        if rows:
            self._conn.executemany("INSERT INTO metrics (ts, step, name, value) VALUES (?, ?, ?, ?)", rows)
        return ""

    def load(self, metric_names: list[str] | None = None) -> pl.DataFrame:
        """Load metrics as a long-format polars DataFrame, ordered by step."""
        if metric_names:
            placeholders = ",".join("?" for _ in metric_names)
            cur = self._conn.execute(
                f"SELECT ts, step, name, value FROM metrics WHERE name IN ({placeholders}) ORDER BY step",
                tuple(metric_names),
            )
        else:
            cur = self._conn.execute("SELECT ts, step, name, value FROM metrics ORDER BY step")
        rows = cur.fetchall()
        if not rows:
            return pl.DataFrame(schema={"timestamp": pl.Int64, "step": pl.Int64, "metric": pl.Utf8, "value": pl.Float64})
        return pl.DataFrame(rows, schema=_SCHEMA, orient="row")

    def flush(self) -> None:
        self._conn.commit()

    def finish(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.commit()
        finally:
            self._conn.close()
