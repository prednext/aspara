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

import io
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("libsql")

from fastapi.testclient import TestClient

from aspara.dashboard.main import app as dashboard_app
from aspara.tenancy import LibsqlTenant, configure_data_dir, configure_libsql_tenant_resolver
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

        # Discovery must include this metadata-only run (no metric rows yet),
        # otherwise home stays empty and /projects/proj 500s via get_runs.
        home = dashboard.get("/", headers=hdr)
        assert home.status_code == 200
        assert "proj" in home.text
        detail = dashboard.get("/projects/proj", headers=hdr)
        assert detail.status_code == 200
        assert "r1" in detail.text

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


def test_remote_libsql_tenant_rejects_artifact_upload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote tenants must not write artifact bytes into the shared data_dir."""
    monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))
    configure_data_dir(str(tmp_path))
    configure_libsql_tenant_resolver(
        lambda t: LibsqlTenant(database="libsql://example") if t == "lib" else None
    )
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        files = {"file": ("model.pt", io.BytesIO(b"weights"), "application/octet-stream")}
        resp = tracker.post(
            "/api/v1/projects/proj/runs/r1/artifacts",
            files=files,
            headers={**hdr, **_CSRF},
        )
        assert resp.status_code == 501
        assert not (tmp_path / "proj" / "r1" / "artifacts" / "model.pt").exists()
        assert list(tmp_path.rglob("model.pt")) == []
    finally:
        configure_libsql_tenant_resolver(None)
        configure_data_dir(None)


def test_local_libsql_tenant_artifact_upload_lands_in_base_dir(tmp_path: Path) -> None:
    """A local libSQL tenant still pins artifact bytes under its base_dir."""
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        created = tracker.post(
            "/api/v1/projects/proj/runs",
            json={"name": "r1"},
            headers={**hdr, **_CSRF},
        )
        assert created.status_code == 200

        files = {"file": ("model.pt", io.BytesIO(b"weights"), "application/octet-stream")}
        resp = tracker.post(
            "/api/v1/projects/proj/runs/r1/artifacts",
            files=files,
            headers={**hdr, **_CSRF},
        )
        assert resp.status_code == 200
        artifact_path = tenant_dir / "proj" / "r1" / "artifacts" / "model.pt"
        assert artifact_path.read_bytes() == b"weights"
    finally:
        configure_libsql_tenant_resolver(None)


def test_libsql_omitted_step_is_stored_as_zero(tmp_path: Path) -> None:
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        r = tracker.post(
            "/api/v1/projects/proj/runs/r1/metrics",
            json={"metrics": {"loss": 1.0}},
            headers={**hdr, **_CSRF},
        )
        assert r.status_code == 200
        got = dashboard.get("/api/projects/proj/runs/metrics?runs=r1", headers=hdr)
        assert got.status_code == 200
        assert _values(got.json(), "loss", "r1") == [1.0]
    finally:
        configure_libsql_tenant_resolver(None)


def test_libsql_non_numeric_metric_is_400(tmp_path: Path) -> None:
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        r = tracker.post(
            "/api/v1/projects/proj/runs/r1/metrics",
            json={"metrics": {"loss": "nope"}, "step": 0},
            headers={**hdr, **_CSRF},
        )
        assert r.status_code == 400
    finally:
        configure_libsql_tenant_resolver(None)


def test_artifact_bytes_removed_when_metadata_write_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}

    def _boom(self: Any, artifact_data: Any) -> None:
        raise RuntimeError("meta down")

    monkeypatch.setattr("aspara.storage.metadata.libsql.LibsqlRunMetadataStorage.add_artifact", _boom)
    try:
        created = tracker.post(
            "/api/v1/projects/proj/runs",
            json={"name": "r1"},
            headers={**hdr, **_CSRF},
        )
        assert created.status_code == 200

        files = {"file": ("model.pt", io.BytesIO(b"weights"), "application/octet-stream")}
        resp = tracker.post(
            "/api/v1/projects/proj/runs/r1/artifacts",
            files=files,
            headers={**hdr, **_CSRF},
        )
        assert resp.status_code == 500
        artifact_path = tenant_dir / "proj" / "r1" / "artifacts" / "model.pt"
        assert not artifact_path.exists()
        assert not artifact_path.with_name("model.pt.partial").exists()
    finally:
        configure_libsql_tenant_resolver(None)


def test_artifact_bytes_removed_when_metadata_connect_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_dir = tmp_path / "lib"
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        created = tracker.post(
            "/api/v1/projects/proj/runs",
            json={"name": "r1"},
            headers={**hdr, **_CSRF},
        )
        assert created.status_code == 200

        def _boom(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("connect failed")

        monkeypatch.setattr("aspara.tracker.router._run_metadata_for_request", _boom)
        files = {"file": ("model.pt", io.BytesIO(b"weights"), "application/octet-stream")}
        resp = tracker.post(
            "/api/v1/projects/proj/runs/r1/artifacts",
            files=files,
            headers={**hdr, **_CSRF},
        )
        assert resp.status_code == 500
        artifact_path = tenant_dir / "proj" / "r1" / "artifacts" / "model.pt"
        assert not artifact_path.exists()
        assert not artifact_path.with_name("model.pt.partial").exists()
    finally:
        configure_libsql_tenant_resolver(None)


def test_invalid_tenant_header_is_rejected() -> None:
    r = tracker.post(
        "/api/v1/projects/proj/runs/r1/metrics",
        json={"metrics": {"loss": 1.0}, "step": 0},
        headers={"X-Aspara-Tenant": "../etc", **_CSRF},
    )
    assert r.status_code == 400
    assert "Invalid tenant" in r.json()["detail"]
