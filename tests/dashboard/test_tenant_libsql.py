"""Dashboard wiring for libSQL-backed tenants (Stage 2 wiring).

A libSQL tenant resolver maps a tenant id to its libSQL database; the catalog
dependencies then serve that tenant through the libSQL-backed facades while the
routes stay unchanged. Exercised over the real HTTP path with the
``X-Aspara-Tenant`` header.

Filesystem tenants must remain unaffected (the libSQL resolver returns None for
them), and libSQL tenants must stay isolated from one another.

Skipped automatically when the optional ``libsql`` package is not installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("libsql")

from fastapi.testclient import TestClient

from aspara.dashboard.dependencies import (
    LibsqlTenant,
    configure_data_dir,
    configure_libsql_tenant_resolver,
)
from aspara.dashboard.main import app
from aspara.storage import create_metrics_storage

client = TestClient(app)

_XHR = {"X-Requested-With": "XMLHttpRequest"}


def _seed_libsql(base_dir: Path, project: str, run: str, series: list[tuple[int, int, dict[str, float]]]) -> None:
    storage = create_metrics_storage(backend="libsql", base_dir=str(base_dir), project_name=project, run_name=run)
    for ts, step, metrics in series:
        storage.save({"timestamp": ts, "step": step, "metrics": metrics})
    storage.close()


def _write_jsonl_run(base: Path, project: str, run: str, series: list[tuple[int, int, dict[str, float]]]) -> None:
    pdir = base / project
    pdir.mkdir(parents=True, exist_ok=True)
    with (pdir / f"{run}.jsonl").open("w") as f:
        for ts, step, metrics in series:
            f.write(json.dumps({"timestamp": ts, "step": step, "metrics": metrics}) + "\n")


def _values(resp_json: dict[str, Any], metric: str, run: str) -> list[float]:
    return resp_json["metrics"][metric][run]["values"]


def test_libsql_tenant_served_over_http(tmp_path: Path) -> None:
    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0}), (2000, 1, {"loss": 0.5})])

    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        # Metrics come from the libSQL database.
        r = client.get("/api/projects/proj/runs/metrics?runs=r1", headers=hdr)
        assert r.status_code == 200
        assert _values(r.json(), "loss", "r1") == [1.0, 0.5]

        # HTML discovery pages render for the libSQL tenant.
        assert client.get("/", headers=hdr).status_code == 200
        detail = client.get("/projects/proj", headers=hdr)
        assert detail.status_code == 200
        assert "r1" in detail.text

        # Run metadata defaults, then update round-trips through libSQL.
        meta = client.get("/api/projects/proj/runs/r1/metadata", headers=hdr)
        assert meta.status_code == 200
        assert meta.json()["tags"] == []

        put = client.put(
            "/api/projects/proj/runs/r1/metadata",
            headers={**hdr, **_XHR},
            json={"tags": ["a", "b"], "notes": "hi"},
        )
        assert put.status_code == 200
        assert put.json()["tags"] == ["a", "b"]
        assert client.get("/api/projects/proj/runs/r1/metadata", headers=hdr).json()["tags"] == ["a", "b"]

        # Project metadata update round-trips too.
        pput = client.put("/api/projects/proj/metadata", headers={**hdr, **_XHR}, json={"tags": ["t"]})
        assert pput.status_code == 200
        assert pput.json()["tags"] == ["t"]

        # Delete removes the run from the libSQL database.
        dele = client.delete("/api/projects/proj/runs/r1", headers={**hdr, **_XHR})
        assert dele.status_code == 204
        gone = client.get("/api/projects/proj/runs/metrics?runs=r1", headers=hdr)
        assert gone.status_code == 200
        assert gone.json()["metrics"] == {}
    finally:
        configure_libsql_tenant_resolver(None)


def test_filesystem_tenant_unaffected_when_libsql_resolver_returns_none(tmp_path: Path) -> None:
    """A libSQL resolver that returns None for a tenant falls back to the filesystem."""
    fs_dir = tmp_path / "fs"
    _write_jsonl_run(fs_dir, "proj", "r", [(1000, 0, {"loss": 7.0})])

    configure_data_dir(str(fs_dir))
    # Resolver only knows about "lib"; the default tenant resolves to None -> filesystem.
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir="/nope") if t == "lib" else None)
    try:
        r = client.get("/api/projects/proj/runs/metrics?runs=r")
        assert r.status_code == 200
        assert _values(r.json(), "loss", "r") == [7.0]
    finally:
        configure_libsql_tenant_resolver(None)
        configure_data_dir(None)


def test_two_libsql_tenants_isolated(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    _seed_libsql(dir_a, "proj", "shared", [(1000, 0, {"loss": 1.0})])
    _seed_libsql(dir_b, "proj", "shared", [(1000, 0, {"loss": 9.0})])

    mapping = {"a": str(dir_a), "b": str(dir_b)}
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=mapping[t]) if t in mapping else None)
    try:
        ra = client.get("/api/projects/proj/runs/metrics?runs=shared", headers={"X-Aspara-Tenant": "a"})
        rb = client.get("/api/projects/proj/runs/metrics?runs=shared", headers={"X-Aspara-Tenant": "b"})
        assert _values(ra.json(), "loss", "shared") == [1.0]
        assert _values(rb.json(), "loss", "shared") == [9.0]
    finally:
        configure_libsql_tenant_resolver(None)
