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
