"""Dashboard-level multi-tenant isolation (Stage 1: tenant wiring).

Exercises the real HTTP path: the tenant middleware sets ``request.state.tenant_id``
from the ``X-Aspara-Tenant`` header, and the catalog dependencies resolve each
tenant to its own data directory. Two tenants must never see each other's data.

No cloud / libSQL needed here — this validates the request -> tenant -> data seam
using the existing file-based catalogs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from aspara.dashboard.dependencies import configure_data_dir, configure_tenant_resolver
from aspara.dashboard.main import app

client = TestClient(app)


def _write_run(base: Path, project: str, run: str, series: list[tuple[int, int, dict[str, float]]]) -> None:
    pdir = base / project
    pdir.mkdir(parents=True, exist_ok=True)
    with (pdir / f"{run}.jsonl").open("w") as f:
        for ts, step, metrics in series:
            f.write(json.dumps({"timestamp": ts, "step": step, "metrics": metrics}) + "\n")
    meta: dict[str, Any] = {
        "run_id": f"{run}_id",
        "tags": [],
        "notes": "",
        "params": {},
        "config": {},
        "artifacts": [],
        "summary": {},
        "is_finished": False,
        "exit_code": None,
        "start_time": None,
        "finish_time": None,
    }
    (pdir / f"{run}.meta.json").write_text(json.dumps(meta))


def _values(resp_json: dict[str, Any], metric: str, run: str) -> list[float]:
    return resp_json["metrics"][metric][run]["values"]


def test_dashboard_isolates_tenants(tmp_path: Path) -> None:
    tenant_a = tmp_path / "tenant_a"
    tenant_b = tmp_path / "tenant_b"

    # Same project/run names, different values.
    _write_run(tenant_a, "proj", "shared", [(1000, 0, {"loss": 1.0}), (2000, 1, {"loss": 0.5})])
    _write_run(tenant_b, "proj", "shared", [(1000, 0, {"loss": 9.0}), (2000, 1, {"loss": 8.0})])
    # A run that only exists for tenant A.
    _write_run(tenant_a, "proj", "onlya", [(1000, 0, {"loss": 42.0})])

    mapping = {"a": str(tenant_a), "b": str(tenant_b)}
    configure_tenant_resolver(lambda t: mapping.get(t, str(tmp_path / "missing")))
    try:
        ra = client.get("/api/projects/proj/runs/metrics?runs=shared", headers={"X-Aspara-Tenant": "a"})
        rb = client.get("/api/projects/proj/runs/metrics?runs=shared", headers={"X-Aspara-Tenant": "b"})
        assert ra.status_code == 200
        assert rb.status_code == 200
        assert _values(ra.json(), "loss", "shared") == [1.0, 0.5]
        assert _values(rb.json(), "loss", "shared") == [9.0, 8.0]

        # A run only in tenant A must be invisible to tenant B (empty metrics).
        rb_secret = client.get("/api/projects/proj/runs/metrics?runs=onlya", headers={"X-Aspara-Tenant": "b"})
        assert rb_secret.status_code == 200
        assert rb_secret.json()["metrics"] == {}

        # ...and visible to tenant A.
        ra_secret = client.get("/api/projects/proj/runs/metrics?runs=onlya", headers={"X-Aspara-Tenant": "a"})
        assert _values(ra_secret.json(), "loss", "onlya") == [42.0]
    finally:
        configure_tenant_resolver(None)
        configure_data_dir(None)


def test_tenant_query_param_sets_cookie_for_browser(tmp_path: Path) -> None:
    """A browser cannot send X-Aspara-Tenant; ?tenant= plus the cookie must work."""
    tenant_a = tmp_path / "tenant_a"
    tenant_b = tmp_path / "tenant_b"
    _write_run(tenant_a, "proj", "shared", [(1000, 0, {"loss": 1.0})])
    _write_run(tenant_b, "proj", "shared", [(1000, 0, {"loss": 9.0})])
    mapping = {"a": str(tenant_a), "b": str(tenant_b)}
    configure_tenant_resolver(lambda t: mapping.get(t, str(tmp_path / "missing")))
    browser = TestClient(app)
    try:
        via_query = browser.get("/api/projects/proj/runs/metrics?runs=shared&tenant=a")
        assert via_query.status_code == 200
        assert _values(via_query.json(), "loss", "shared") == [1.0]
        assert via_query.cookies.get("aspara_tenant") == "a"

        # Later same-origin requests (no query, no header) keep the cookie tenant.
        via_cookie = browser.get("/api/projects/proj/runs/metrics?runs=shared")
        assert _values(via_cookie.json(), "loss", "shared") == [1.0]

        # Header still wins over the cookie.
        via_header = browser.get(
            "/api/projects/proj/runs/metrics?runs=shared",
            headers={"X-Aspara-Tenant": "b"},
        )
        assert _values(via_header.json(), "loss", "shared") == [9.0]
    finally:
        configure_tenant_resolver(None)
        configure_data_dir(None)


def test_default_tenant_behavior_unchanged_without_resolver(tmp_path: Path) -> None:
    """With no resolver, the tenant header is informational and the single
    configured data directory is always used (backward compatible)."""
    _write_run(tmp_path, "proj", "r", [(1000, 0, {"loss": 1.0})])
    configure_data_dir(str(tmp_path))
    try:
        # No tenant header.
        r = client.get("/api/projects/proj/runs/metrics?runs=r")
        assert r.status_code == 200
        assert _values(r.json(), "loss", "r") == [1.0]

        # A tenant header is ignored when no resolver is installed.
        r2 = client.get("/api/projects/proj/runs/metrics?runs=r", headers={"X-Aspara-Tenant": "anything"})
        assert r2.status_code == 200
        assert _values(r2.json(), "loss", "r") == [1.0]
    finally:
        configure_data_dir(None)


def test_invalid_tenant_id_is_rejected(tmp_path: Path) -> None:
    """A present but unsafe tenant id is 400, not silently the default tenant."""
    _write_run(tmp_path, "proj", "r", [(1000, 0, {"loss": 1.0})])
    configure_data_dir(str(tmp_path))
    browser = TestClient(app)
    try:
        via_query = browser.get("/api/projects/proj/runs/metrics?runs=r&tenant=../etc")
        assert via_query.status_code == 400
        assert "Invalid tenant" in via_query.json()["detail"]

        via_header = browser.get(
            "/api/projects/proj/runs/metrics?runs=r",
            headers={"X-Aspara-Tenant": "my.tenant"},
        )
        assert via_header.status_code == 400

        # After the 400, a request with no tenant still reaches the default data.
        ok = browser.get("/api/projects/proj/runs/metrics?runs=r")
        assert ok.status_code == 200
        assert _values(ok.json(), "loss", "r") == [1.0]
    finally:
        configure_data_dir(None)
