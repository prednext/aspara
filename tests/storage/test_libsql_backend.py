"""Tests for the libsql metrics backend (multi-tenant SaaS path, first slice).

These run against local libSQL database files (no network), which is enough to
de-risk the core thesis: a tenant dimension in front of the storage factory gives
complete isolation, and the libsql backend is a drop-in for the wide-format contract.

Skipped automatically if the optional ``libsql`` package is not installed.
"""

from __future__ import annotations

from typing import Any

import pytest
from polars.testing import assert_frame_equal

pytest.importorskip("libsql")

from aspara.exceptions import RunNotFoundError
from aspara.storage import create_metrics_storage
from aspara.storage.metrics.libsql import LibsqlMetricsStorage


def _md(ts: int, step: int, **metrics: float) -> dict[str, Any]:
    return {"timestamp": ts, "step": step, "metrics": metrics}


def _write(storage: Any, records: list[dict[str, Any]]) -> None:
    for rec in records:
        storage.save(rec)


def test_factory_creates_libsql_storage(tmp_path: Any) -> None:
    storage = create_metrics_storage(
        backend="libsql",
        base_dir=str(tmp_path),
        project_name="p",
        run_name="r",
    )
    assert isinstance(storage, LibsqlMetricsStorage)


def test_two_tenants_are_isolated(tmp_path: Any) -> None:
    """Two tenants (two local DBs) with identical project/run names never leak."""
    tenant_a = tmp_path / "tenant_a"
    tenant_b = tmp_path / "tenant_b"

    a = create_metrics_storage(backend="libsql", base_dir=str(tenant_a), project_name="proj", run_name="run1")
    b = create_metrics_storage(backend="libsql", base_dir=str(tenant_b), project_name="proj", run_name="run1")

    # Same names, different values.
    _write(a, [_md(1000, 0, loss=1.0), _md(2000, 1, loss=0.5)])
    _write(b, [_md(1000, 0, loss=9.0), _md(2000, 1, loss=8.0)])

    df_a = a.load()
    df_b = b.load()

    assert df_a["_loss"].to_list() == [1.0, 0.5]
    assert df_b["_loss"].to_list() == [9.0, 8.0]

    # A run that exists only in tenant A must be invisible from tenant B.
    a_only = create_metrics_storage(backend="libsql", base_dir=str(tenant_a), project_name="proj", run_name="secret")
    _write(a_only, [_md(1000, 0, loss=42.0)])

    b_probe = create_metrics_storage(backend="libsql", base_dir=str(tenant_b), project_name="proj", run_name="secret")
    with pytest.raises(RunNotFoundError):
        b_probe.load()


def test_wide_format_matches_jsonl(tmp_path: Any) -> None:
    """libsql.load() returns the same wide frame as the jsonl backend."""
    records = [
        _md(1000, 0, loss=1.5, acc=0.1),
        _md(2000, 1, loss=1.0, acc=0.2),
        _md(3000, 2, loss=0.5, acc=0.3),
    ]

    jsonl = create_metrics_storage(backend="jsonl", base_dir=str(tmp_path / "j"), project_name="p", run_name="r")
    libsql = create_metrics_storage(backend="libsql", base_dir=str(tmp_path / "l"), project_name="p", run_name="r")
    _write(jsonl, records)
    _write(libsql, records)

    df_jsonl = jsonl.load()
    df_libsql = libsql.load()

    assert_frame_equal(
        df_jsonl,
        df_libsql,
        check_column_order=False,
        check_dtypes=False,
    )


def test_metric_name_filter(tmp_path: Any) -> None:
    storage = create_metrics_storage(backend="libsql", base_dir=str(tmp_path), project_name="p", run_name="r")
    _write(storage, [_md(1000, 0, loss=1.0, acc=0.9), _md(2000, 1, loss=0.5, acc=0.95)])

    df = storage.load(metric_names=["loss"])
    assert "_loss" in df.columns
    assert "_acc" not in df.columns
    assert df["_loss"].to_list() == [1.0, 0.5]


def test_run_not_found(tmp_path: Any) -> None:
    storage = create_metrics_storage(backend="libsql", base_dir=str(tmp_path), project_name="p", run_name="missing")
    with pytest.raises(RunNotFoundError):
        storage.load()
