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

import io
import json
import zipfile
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


def test_libsql_tenant_local_artifact_zip_download(tmp_path: Path) -> None:
    """Model files stay on the tenant's local disk; ZIP download reads them.

    A libSQL tenant keeps its metrics/metadata in libSQL but its artifact bytes
    live locally under ``{base_dir}/{project}/{run}/artifacts`` (the "model files
    local" design). The download route resolves that local dir via the tenant's
    data directory, so a ZIP is streamed back for the libSQL tenant.
    """
    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])

    # Artifact bytes on the tenant's local disk (as a local run would write them).
    artifacts_dir = tenant_dir / "proj" / "r1" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "config.json": b'{"lr": 0.01}',
        "best_model.pt": b"binary-model-bytes",
    }
    for fname, body in files.items():
        (artifacts_dir / fname).write_bytes(body)

    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        resp = client.get("/api/projects/proj/runs/r1/artifacts/download", headers=hdr)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            assert sorted(zf.namelist()) == ["best_model.pt", "config.json"]
            assert zf.read("best_model.pt") == files["best_model.pt"]
            assert zf.read("config.json") == files["config.json"]
    finally:
        configure_libsql_tenant_resolver(None)


def test_libsql_tenant_without_artifacts_returns_404(tmp_path: Path) -> None:
    """A libSQL tenant run with no local artifacts area yields the historical 404."""
    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])

    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    try:
        resp = client.get("/api/projects/proj/runs/r1/artifacts/download", headers={"X-Aspara-Tenant": "lib"})
        assert resp.status_code == 404
    finally:
        configure_libsql_tenant_resolver(None)


def test_remote_libsql_tenant_artifact_zip_is_404(tmp_path: Path) -> None:
    """Remote tenants have no local artifact bytes; ZIP must not read the default data_dir."""
    configure_data_dir(str(tmp_path))
    leaked = tmp_path / "proj" / "r1" / "artifacts"
    leaked.mkdir(parents=True, exist_ok=True)
    (leaked / "secret.pt").write_bytes(b"should-not-be-served")

    configure_libsql_tenant_resolver(
        lambda t: LibsqlTenant(database="libsql://example") if t == "lib" else None
    )
    try:
        resp = client.get(
            "/api/projects/proj/runs/r1/artifacts/download",
            headers={"X-Aspara-Tenant": "lib"},
        )
        assert resp.status_code == 404
    finally:
        configure_libsql_tenant_resolver(None)
        configure_data_dir(None)


def _write_artifacts(base: Path, project: str, run: str, files: dict[str, bytes]) -> Path:
    artifacts_dir = base / project / run / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (artifacts_dir / name).write_bytes(body)
    return artifacts_dir


def test_local_libsql_delete_run_removes_artifact_bytes(tmp_path: Path) -> None:
    """DELETE a local libSQL run must remove its artifact dir, not aspara.db."""
    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])
    _seed_libsql(tenant_dir, "proj", "keep", [(1000, 0, {"loss": 2.0})])
    artifacts_dir = _write_artifacts(tenant_dir, "proj", "r1", {"old.pt": b"stale-weights"})
    keep_dir = _write_artifacts(tenant_dir, "proj", "keep", {"ok.pt": b"keep"})

    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib", **_XHR}
    try:
        resp = client.delete("/api/projects/proj/runs/r1", headers=hdr)
        assert resp.status_code == 204
        assert not artifacts_dir.exists()
        assert not (tenant_dir / "proj" / "r1").exists()
        assert (keep_dir / "ok.pt").read_bytes() == b"keep"
        assert (tenant_dir / "aspara.db").exists()
        zip_resp = client.get("/api/projects/proj/runs/r1/artifacts/download", headers={"X-Aspara-Tenant": "lib"})
        assert zip_resp.status_code == 404
    finally:
        configure_libsql_tenant_resolver(None)


def test_local_libsql_delete_run_same_name_recreate_does_not_mix_artifacts(tmp_path: Path) -> None:
    """Recreating a deleted run must not ZIP leftover model files from the old run."""
    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])
    _write_artifacts(tenant_dir, "proj", "r1", {"old.pt": b"stale-weights"})

    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        dele = client.delete("/api/projects/proj/runs/r1", headers={**hdr, **_XHR})
        assert dele.status_code == 204

        _seed_libsql(tenant_dir, "proj", "r1", [(2000, 0, {"loss": 0.1})])
        zip_resp = client.get("/api/projects/proj/runs/r1/artifacts/download", headers=hdr)
        assert zip_resp.status_code == 404
        assert not (tenant_dir / "proj" / "r1" / "artifacts" / "old.pt").exists()
    finally:
        configure_libsql_tenant_resolver(None)


def test_local_libsql_delete_project_removes_artifact_dirs_not_db(tmp_path: Path) -> None:
    """DELETE a local libSQL project removes every run's files and leaves aspara.db."""
    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])
    _seed_libsql(tenant_dir, "proj", "r2", [(1000, 0, {"loss": 2.0})])
    _seed_libsql(tenant_dir, "other", "r1", [(1000, 0, {"loss": 9.0})])
    _write_artifacts(tenant_dir, "proj", "r1", {"a.pt": b"a"})
    _write_artifacts(tenant_dir, "proj", "r2", {"b.pt": b"b"})
    other_dir = _write_artifacts(tenant_dir, "other", "r1", {"c.pt": b"c"})

    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    try:
        resp = client.delete("/api/projects/proj", headers={"X-Aspara-Tenant": "lib", **_XHR})
        assert resp.status_code == 204
        assert not (tenant_dir / "proj").exists()
        assert (tenant_dir / "aspara.db").exists()
        assert (other_dir / "c.pt").read_bytes() == b"c"
    finally:
        configure_libsql_tenant_resolver(None)


def test_local_libsql_delete_keeps_run_when_artifact_bytes_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If rmtree fails, the DB row must still be there so delete can be retried."""
    from aspara.storage.artifacts.filesystem import FilesystemArtifactStore

    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])
    artifacts_dir = _write_artifacts(tenant_dir, "proj", "r1", {"old.pt": b"stale-weights"})

    def _boom(self: FilesystemArtifactStore, project: str, run: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(FilesystemArtifactStore, "delete_run", _boom)
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        resp = client.delete("/api/projects/proj/runs/r1", headers={**hdr, **_XHR})
        assert resp.status_code == 500
        assert (artifacts_dir / "old.pt").read_bytes() == b"stale-weights"
        got = client.get("/api/projects/proj/runs/metrics?runs=r1", headers=hdr)
        assert _values(got.json(), "loss", "r1") == [1.0]
    finally:
        configure_libsql_tenant_resolver(None)


def test_local_libsql_delete_retries_after_db_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bytes are removed first; a later DB failure must not block a retry."""
    from aspara.catalog.libsql_catalog import LibsqlCatalog

    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])
    artifacts_dir = _write_artifacts(tenant_dir, "proj", "r1", {"old.pt": b"stale-weights"})

    calls = {"n": 0}
    real = LibsqlCatalog.delete_run

    def _flaky(self: LibsqlCatalog, project: str, run: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("db down")
        return real(self, project, run)

    monkeypatch.setattr(LibsqlCatalog, "delete_run", _flaky)
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    hdr = {"X-Aspara-Tenant": "lib"}
    try:
        first = client.delete("/api/projects/proj/runs/r1", headers={**hdr, **_XHR})
        assert first.status_code == 500
        assert not artifacts_dir.exists()
        got = client.get("/api/projects/proj/runs/metrics?runs=r1", headers=hdr)
        assert _values(got.json(), "loss", "r1") == [1.0]

        second = client.delete("/api/projects/proj/runs/r1", headers={**hdr, **_XHR})
        assert second.status_code == 204
        gone = client.get("/api/projects/proj/runs/metrics?runs=r1", headers=hdr)
        assert gone.json()["metrics"] == {}
    finally:
        configure_libsql_tenant_resolver(None)


def test_null_artifacts_do_not_500_run_detail(tmp_path: Path) -> None:
    """A run_meta row with null artifacts/params must still render the run page."""
    from aspara.catalog import LibsqlCatalog

    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "broken", [(1000, 0, {"loss": 1.0})])
    cat = LibsqlCatalog(base_dir=str(tenant_dir))
    try:
        cat._execute(
            "INSERT INTO run_meta (project, run, data) VALUES (?, ?, ?)",
            (
                "proj",
                "broken",
                '{"run_id": "x", "tags": null, "artifacts": null, "params": null, "config": null}',
            ),
        )
        cat._conn.commit()
    finally:
        cat.close()

    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(tenant_dir)) if t == "lib" else None)
    try:
        page = client.get("/projects/proj/runs/broken", headers={"X-Aspara-Tenant": "lib"})
        assert page.status_code == 200
        assert "broken" in page.text
    finally:
        configure_libsql_tenant_resolver(None)


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


def test_libsql_catalog_cache_shares_one_connection_on_concurrent_miss(tmp_path: Path) -> None:
    """Two overlapping first requests for the same tenant must not leak a connection."""
    import threading

    from aspara.catalog import libsql_catalog as catalog_mod
    from aspara.dashboard import dependencies as deps

    tenant_dir = tmp_path / "lib"
    _seed_libsql(tenant_dir, "proj", "r1", [(1000, 0, {"loss": 1.0})])

    connects = {"n": 0}
    orig_connect = catalog_mod.connect_libsql

    def _connect(*args: Any, **kwargs: Any) -> Any:
        connects["n"] += 1
        return orig_connect(*args, **kwargs)

    catalog_mod.connect_libsql = _connect  # type: ignore[method-assign]
    deps._clear_catalog_caches()
    try:
        results: list[Any] = []
        errors: list[BaseException] = []

        def _borrow() -> None:
            try:
                catalogs, release = deps._borrow_libsql_catalogs(str(tenant_dir), None, None, None)
                results.append((catalogs, release))
            except BaseException as e:
                errors.append(e)

        threads = [threading.Thread(target=_borrow) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert errors == []
        assert connects["n"] == 1
        assert len(results) == 8
        first = results[0][0][0]
        assert all(catalogs[0] is first for catalogs, _ in results)
        for _, release in results:
            release()
    finally:
        catalog_mod.connect_libsql = orig_connect  # type: ignore[method-assign]
        deps._clear_catalog_caches()
