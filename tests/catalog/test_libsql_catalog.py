"""Tests for LibsqlCatalog - project/run discovery over a libSQL tenant DB.

Runs against local libSQL database files (no network). Validates that projects
and runs are derived from the metrics table, that timestamps surface as UTC
datetimes, that discovery is isolated per tenant database, and that a freshly
provisioned (empty) database yields empty listings rather than erroring.

Skipped automatically when the optional ``libsql`` package is not installed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

pytest.importorskip("libsql")

from aspara.catalog import LibsqlCatalog
from aspara.exceptions import ProjectNotFoundError, RunNotFoundError
from aspara.storage import create_metrics_storage


def _md(ts: int, step: int, **metrics: float) -> dict[str, Any]:
    return {"timestamp": ts, "step": step, "metrics": metrics}


def _seed(base_dir: Any, project: str, run: str, records: list[dict[str, Any]]) -> None:
    storage = create_metrics_storage(backend="libsql", base_dir=str(base_dir), project_name=project, run_name=run)
    for rec in records:
        storage.save(rec)
    storage.close()


def test_empty_database_lists_nothing(tmp_path: Any) -> None:
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        assert cat.get_projects() == []
    finally:
        cat.close()


def test_get_projects_counts_runs_and_last_update(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run1", [_md(1000, 0, loss=1.0)])
    _seed(tmp_path, "alpha", "run2", [_md(5000, 0, loss=2.0)])
    _seed(tmp_path, "beta", "run1", [_md(3000, 0, loss=3.0)])

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        projects = cat.get_projects()
        by_name = {p.name: p for p in projects}

        assert [p.name for p in projects] == ["alpha", "beta"]  # sorted
        assert by_name["alpha"].run_count == 2
        assert by_name["beta"].run_count == 1
        # last_update is the max metric timestamp (5000 ms) for alpha.
        assert by_name["alpha"].last_update == datetime(1970, 1, 1, 0, 0, 5, tzinfo=timezone.utc)
    finally:
        cat.close()


def test_get_runs_lists_runs_with_times(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run_b", [_md(2000, 0, loss=1.0), _md(4000, 1, loss=0.5)])
    _seed(tmp_path, "alpha", "run_a", [_md(1000, 0, loss=9.0)])

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        runs = cat.get_runs("alpha")
        assert [r.name for r in runs] == ["run_a", "run_b"]  # sorted

        run_b = next(r for r in runs if r.name == "run_b")
        assert run_b.start_time == datetime(1970, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
        assert run_b.last_update == datetime(1970, 1, 1, 0, 0, 4, tzinfo=timezone.utc)
    finally:
        cat.close()


def test_get_runs_unknown_project_raises(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run1", [_md(1000, 0, loss=1.0)])
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        with pytest.raises(ProjectNotFoundError):
            cat.get_runs("does_not_exist")
    finally:
        cat.close()


def test_metadata_only_run_is_discoverable(tmp_path: Any) -> None:
    """create_run writes run_meta with no metric rows; listings must still show it."""
    from aspara.storage.metadata.libsql import LibsqlRunMetadataStorage

    storage = LibsqlRunMetadataStorage(str(tmp_path), "alpha", "init_only")
    try:
        storage.set_init(run_id="abc123", tags=["exp"], notes="", timestamp=1000)
    finally:
        storage.close()

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        projects = cat.get_projects()
        assert [p.name for p in projects] == ["alpha"]
        assert projects[0].run_count == 1
        assert cat.project_exists("alpha")

        runs = cat.get_runs("alpha")
        assert [r.name for r in runs] == ["init_only"]
        assert runs[0].run_id == "abc123"
        assert runs[0].tags == ["exp"]
        assert projects[0].last_update == datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc)

        run = cat.get_run("alpha", "init_only")
        assert run.name == "init_only"
    finally:
        cat.close()


def test_metadata_only_run_does_not_double_count_metrics(tmp_path: Any) -> None:
    """A run with both metrics and metadata still counts once; a sibling init is extra."""
    from aspara.storage.metadata.libsql import LibsqlRunMetadataStorage

    _seed(tmp_path, "alpha", "logged", [_md(1000, 0, loss=1.0)])
    storage = LibsqlRunMetadataStorage(str(tmp_path), "alpha", "init_only")
    try:
        storage.set_init(run_id="only", tags=[], notes="", timestamp=2000)
    finally:
        storage.close()

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        by_name = {p.name: p for p in cat.get_projects()}
        assert by_name["alpha"].run_count == 2
        assert {r.name for r in cat.get_runs("alpha")} == {"logged", "init_only"}
    finally:
        cat.close()


def test_load_metrics_wide_and_start_time_filter(tmp_path: Any) -> None:
    _seed(
        tmp_path,
        "alpha",
        "run1",
        [_md(1000, 0, loss=1.5, acc=0.1), _md(2000, 1, loss=1.0, acc=0.2), _md(3000, 2, loss=0.5, acc=0.3)],
    )

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        df = cat.load_metrics("alpha", "run1")
        assert set(df.columns) >= {"timestamp", "step", "_loss", "_acc"}
        assert df["_loss"].to_list() == [1.5, 1.0, 0.5]

        cutoff = datetime(1970, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
        df2 = cat.load_metrics("alpha", "run1", start_time=cutoff)
        assert df2["_loss"].to_list() == [1.0, 0.5]

        # Unknown run -> empty frame (not an error), mirroring the file catalog.
        empty = cat.load_metrics("alpha", "missing")
        assert len(empty) == 0
        assert set(empty.columns) == {"timestamp", "step"}
    finally:
        cat.close()


def test_two_tenants_are_isolated(tmp_path: Any) -> None:
    tenant_a = tmp_path / "a"
    tenant_b = tmp_path / "b"
    _seed(tenant_a, "proj", "shared", [_md(1000, 0, loss=1.0)])
    _seed(tenant_a, "proj", "onlya", [_md(1000, 0, loss=42.0)])
    _seed(tenant_b, "proj", "shared", [_md(1000, 0, loss=9.0)])

    cat_a = LibsqlCatalog(base_dir=str(tenant_a))
    cat_b = LibsqlCatalog(base_dir=str(tenant_b))
    try:
        assert {r.name for r in cat_a.get_runs("proj")} == {"shared", "onlya"}
        assert {r.name for r in cat_b.get_runs("proj")} == {"shared"}
        assert cat_a.load_metrics("proj", "shared")["_loss"].to_list() == [1.0]
        assert cat_b.load_metrics("proj", "shared")["_loss"].to_list() == [9.0]
        # Tenant A's secret run is invisible to tenant B (empty frame).
        assert len(cat_b.load_metrics("proj", "onlya")) == 0
    finally:
        cat_a.close()
        cat_b.close()


def test_run_metadata_defaults_when_absent(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run1", [_md(1000, 0, loss=1.0)])
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        meta = cat.get_run_metadata("alpha", "run1")
        assert meta["tags"] == []
        assert meta["notes"] == ""
        assert meta["status"] == "wip"
        # An enriched RunInfo carries the defaults too.
        run = cat.get_runs("alpha")[0]
        assert run.tags == []
        assert run.param_count == 0
    finally:
        cat.close()


def test_run_metadata_roundtrip_and_enrichment(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run1", [_md(1000, 0, loss=1.0)])
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        updated = cat.update_run_metadata("alpha", "run1", {"tags": ["a", "b"], "notes": "hello"})
        assert updated["tags"] == ["a", "b"]
        assert updated["notes"] == "hello"

        # Persisted and reflected in listings.
        assert cat.get_run_metadata("alpha", "run1")["tags"] == ["a", "b"]
        run = cat.get_runs("alpha")[0]
        assert run.tags == ["a", "b"]

        assert cat.delete_run_metadata("alpha", "run1") is True
        assert cat.delete_run_metadata("alpha", "run1") is False
        assert cat.get_run_metadata("alpha", "run1")["tags"] == []
    finally:
        cat.close()


def test_update_run_metadata_validation(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run1", [_md(1000, 0, loss=1.0)])
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        with pytest.raises(ValueError):
            cat.update_run_metadata("alpha", "run1", {"tags": "not-a-list"})
    finally:
        cat.close()


def test_delete_run_removes_metrics_and_metadata(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "keep", [_md(1000, 0, loss=1.0)])
    _seed(tmp_path, "alpha", "gone", [_md(1000, 0, loss=2.0)])
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        cat.update_run_metadata("alpha", "gone", {"tags": ["x"]})
        cat.delete_run("alpha", "gone")

        assert {r.name for r in cat.get_runs("alpha")} == {"keep"}
        assert len(cat.load_metrics("alpha", "gone")) == 0
        assert cat.get_run_metadata("alpha", "gone")["tags"] == []  # meta gone -> defaults

        with pytest.raises(RunNotFoundError):
            cat.delete_run("alpha", "gone")
    finally:
        cat.close()


def test_project_metadata_roundtrip(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run1", [_md(1000, 0, loss=1.0)])
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        updated = cat.update_project_metadata("alpha", {"notes": "proj notes", "tags": ["t1"]})
        assert updated["notes"] == "proj notes"
        assert updated["tags"] == ["t1"]
        assert updated["created_at"] is not None
        assert updated["updated_at"] is not None

        pairs = cat.get_projects_with_metadata()
        by_name = {p.name: meta for p, meta in pairs}
        assert by_name["alpha"]["tags"] == ["t1"]

        assert cat.delete_project_metadata("alpha") is True
        assert cat.delete_project_metadata("alpha") is False
    finally:
        cat.close()


def test_delete_project_removes_everything(tmp_path: Any) -> None:
    _seed(tmp_path, "alpha", "run1", [_md(1000, 0, loss=1.0)])
    _seed(tmp_path, "beta", "run1", [_md(1000, 0, loss=2.0)])
    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        cat.update_project_metadata("alpha", {"tags": ["t"]})
        cat.update_run_metadata("alpha", "run1", {"tags": ["r"]})

        cat.delete_project("alpha")

        assert [p.name for p in cat.get_projects()] == ["beta"]
        assert cat.get_project_metadata("alpha")["tags"] == []
        with pytest.raises(RunNotFoundError):
            cat.delete_run("alpha", "run1")

        with pytest.raises(ProjectNotFoundError):
            cat.delete_project("alpha")
    finally:
        cat.close()


def test_null_tags_and_artifacts_do_not_crash_listing(tmp_path: Any) -> None:
    """A parseable run_meta row with tags/artifacts null must not 500 the project page."""
    from aspara.storage.metadata.libsql import LibsqlRunMetadataStorage

    storage = LibsqlRunMetadataStorage(str(tmp_path), "alpha", "broken")
    try:
        storage.set_init(run_id="x", tags=["ok"], notes="", timestamp=1000)
    finally:
        storage.close()
    _seed(tmp_path, "alpha", "healthy", [_md(2000, 0, loss=1.0)])

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        cat._execute(
            "UPDATE run_meta SET data = ? WHERE project = ? AND run = ?",
            ('{"run_id": "x", "tags": null, "artifacts": null}', "alpha", "broken"),
        )
        cat._conn.commit()
        runs = cat.get_runs("alpha")
        by_name = {r.name: r for r in runs}
        assert "healthy" in by_name
        assert by_name["broken"].tags == []
        assert by_name["broken"].artifact_count == 0
        assert by_name["broken"].is_corrupted is True
        assert cat.get_run("alpha", "broken").is_corrupted is True
    finally:
        cat.close()


@pytest.mark.asyncio
async def test_libsql_subscribe_stays_open_until_cancelled(tmp_path: Any) -> None:
    """Empty subscribe must not return immediately (that retriggers EventSource)."""
    from aspara.catalog import LibsqlRunCatalog

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    adapter = LibsqlRunCatalog(cat)
    gen = adapter.subscribe({"alpha": ["r1"]}, datetime.now(timezone.utc))
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(gen), timeout=0.05)
    finally:
        await gen.aclose()
        cat.close()


def test_execute_reopens_dead_connection(tmp_path: Any) -> None:
    class _Dead:
        def execute(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("connection closed")

        def close(self) -> None:
            return None

    cat = LibsqlCatalog(base_dir=str(tmp_path))
    try:
        cat._conn = _Dead()
        assert cat.get_projects() == []
        assert cat.get_projects() == []
    finally:
        cat.close()
