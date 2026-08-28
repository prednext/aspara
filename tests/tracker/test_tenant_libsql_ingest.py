"""Tracker ingestion for libSQL-backed tenants (multi-tenant SaaS write path).

A libSQL tenant resolver maps a tenant id to its libSQL database. The tracker
(mounted as its own app, without the dashboard's tenant middleware) reads the
``X-Aspara-Tenant`` header directly and routes metric writes to that tenant's
libSQL database. The dashboard then reads the same database back, so metrics
ingested over HTTP become visible (and, later, live) for the libSQL tenant.

Filesystem tenants must remain unaffected (the libSQL resolver returns None).

Skipped automatically when the optional ``libsql`` package is not installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("libsql")

from fastapi.testclient import TestClient

from aspara.dashboard.main import app as dashboard_app
from aspara.tenancy import LibsqlTenant, configure_libsql_tenant_resolver
from aspara.tracker.main import app as tracker_app

tracker = TestClient(tracker_app)
dashboard = TestClient(dashboard_app)

_CSRF = {"X-Requested-With": "XMLHttpRequest"}


def _values(resp_json: dict[str, Any], metric: str, run: str) -> list[float]:
    return resp_json["metrics"][metric][run]["values"]


def test_libsql_tenant_metrics_ingested_and_served(tmp_path: Path) -> None:
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        # Ingest two steps over the tracker HTTP API for the libSQL tenant.
        for step, loss in ((0, 1.0), (1, 0.5)):
            r = tracker.post(
                "/api/v1/projects/proj/runs/r1/metrics",
                json={"metrics": {"loss": loss}, "step": step},
                headers={**hdr, **_CSRF},
            )
            assert r.status_code == 200

        # Writes went to the tenant's libSQL database, not a jsonl file.
        assert (tenant_dir / "aspara.db").exists()
        assert not (tenant_dir / "proj" / "r1.jsonl").exists()

        # The dashboard reads the same libSQL database back for this tenant.
        got = dashboard.get("/api/projects/proj/runs/metrics?runs=r1", headers=hdr)
        assert got.status_code == 200
        assert _values(got.json(), "loss", "r1") == [1.0, 0.5]
    finally:
        configure_libsql_tenant_resolver(None)


def test_filesystem_tenant_unaffected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a libSQL resolver that returns None for the default tenant, writes stay on disk."""
    monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir="/nope") if t == "lib" else None)
    try:
        r = tracker.post(
            "/api/v1/projects/proj/runs/r/metrics",
            json={"metrics": {"loss": 7.0}, "step": 0},
            headers=_CSRF,
        )
        assert r.status_code == 200
        # Default tenant resolves to None -> filesystem: a jsonl file is written.
        assert (tmp_path / "proj" / "r.jsonl").exists()
    finally:
        configure_libsql_tenant_resolver(None)


def test_libsql_tenant_metadata_ingested_and_served(tmp_path: Path) -> None:
    """create_run/config/summary/tags/finish over the tracker land in the tenant's libSQL DB.

    The dashboard then reads the same database back, so run metadata written by the
    tracker (a separate app) becomes visible for the libSQL tenant. No ``*.meta.json``
    file is written for a libSQL tenant.
    """
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        created = tracker.post(
            "/api/v1/projects/proj/runs",
            json={
                "name": "r1",
                "tags": ["exp"],
                "notes": "hello",
                "config": {"lr": 0.01},
                "project_tags": ["team-a"],
            },
            headers={**hdr, **_CSRF},
        )
        assert created.status_code == 200
        run_id = created.json()["run_id"]
        assert run_id

        # No filesystem metadata file for a libSQL tenant; it lives in the DB.
        assert not (tenant_dir / "proj" / "r1.meta.json").exists()

        # The dashboard reads the run metadata back from the same libSQL database.
        meta = dashboard.get("/api/projects/proj/runs/r1/metadata", headers=hdr).json()
        assert meta["run_id"] == run_id
        assert meta["tags"] == ["exp"]
        assert meta["notes"] == "hello"
        assert meta["config"] == {"lr": 0.01}
        assert meta["is_finished"] is False

        # Project-level tags round-trip too.
        pmeta = dashboard.get("/api/projects/proj/metadata", headers=hdr).json()
        assert pmeta["tags"] == ["team-a"]

        # Config merges, summary is stored, tags are replaced.
        assert tracker.post(
            "/api/v1/projects/proj/runs/r1/config",
            json={"config": {"batch": 32}},
            headers={**hdr, **_CSRF},
        ).status_code == 200
        assert tracker.post(
            "/api/v1/projects/proj/runs/r1/summary",
            json={"summary": {"best_loss": 0.1}},
            headers={**hdr, **_CSRF},
        ).status_code == 200
        assert tracker.post(
            "/api/v1/projects/proj/runs/r1/tags",
            json={"tags": ["final"]},
            headers={**hdr, **_CSRF},
        ).status_code == 200

        meta = dashboard.get("/api/projects/proj/runs/r1/metadata", headers=hdr).json()
        assert meta["config"] == {"lr": 0.01, "batch": 32}
        assert meta["summary"] == {"best_loss": 0.1}
        assert meta["tags"] == ["final"]

        # Finishing the run updates status/exit_code in libSQL.
        assert tracker.post(
            "/api/v1/projects/proj/runs/r1/finish",
            json={"exit_code": 0},
            headers={**hdr, **_CSRF},
        ).status_code == 200
        meta = dashboard.get("/api/projects/proj/runs/r1/metadata", headers=hdr).json()
        assert meta["is_finished"] is True
        assert meta["exit_code"] == 0
    finally:
        configure_libsql_tenant_resolver(None)


def test_libsql_tenant_create_run_conflict_and_resume(tmp_path: Path) -> None:
    """A duplicate create_run 409s unless ``resume`` is set, which resets finish state."""
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        first = tracker.post(
            "/api/v1/projects/proj/runs",
            json={"name": "r1"},
            headers={**hdr, **_CSRF},
        )
        assert first.status_code == 200
        run_id = first.json()["run_id"]

        # Finish it, then a plain re-create conflicts.
        tracker.post("/api/v1/projects/proj/runs/r1/finish", json={"exit_code": 0}, headers={**hdr, **_CSRF})
        conflict = tracker.post("/api/v1/projects/proj/runs", json={"name": "r1"}, headers={**hdr, **_CSRF})
        assert conflict.status_code == 409

        # Resume reuses the run_id and clears the finish state.
        resumed = tracker.post(
            "/api/v1/projects/proj/runs",
            json={"name": "r1", "resume": True},
            headers={**hdr, **_CSRF},
        )
        assert resumed.status_code == 200
        assert resumed.json()["run_id"] == run_id

        meta = dashboard.get("/api/projects/proj/runs/r1/metadata", headers=hdr).json()
        assert meta["is_finished"] is False
    finally:
        configure_libsql_tenant_resolver(None)


def test_filesystem_tenant_metadata_unaffected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A filesystem tenant still writes a ``*.meta.json`` file (no libSQL DB)."""
    monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir="/nope") if t == "lib" else None)
    try:
        created = tracker.post(
            "/api/v1/projects/proj/runs",
            json={"name": "r", "tags": ["x"]},
            headers=_CSRF,
        )
        assert created.status_code == 200
        assert (tmp_path / "proj" / "r.meta.json").exists()
        assert not (tmp_path / "aspara.db").exists()
    finally:
        configure_libsql_tenant_resolver(None)
