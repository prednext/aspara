"""End-to-end demo of the multi-tenant libSQL flow.

Two tenants are served side by side, selected per request by the
``X-Aspara-Tenant`` header:

- ``lib``: libSQL-backed. By default its metrics/metadata live in a local
  ``{demo_dir}/lib/aspara.db``. With ``--cloud`` they go to a Turso Cloud
  database instead (``TURSO_DATABASE_URL`` + ``TURSO_AUTH_TOKEN``); remote
  tenants do not store artifact bytes.
- ``fs``: filesystem-backed. Its data lives as ``*.jsonl`` / ``*.meta.json``
  files under ``{demo_dir}/fs/fs``.

The tracker (write path, mounted at ``/tracker``) and the dashboard (read path,
mounted at ``/``) share the same process-global tenant resolver, so metrics
logged over the tracker HTTP API for the libSQL tenant are written to its libSQL
database and then read back by the dashboard -- fully isolated from the
filesystem tenant.

Usage:
    # Fast, self-contained proof via FastAPI TestClient (ingest + read back):
    uv run python examples/demo_libsql_tenant.py verify

    # Same proof against a real Turso Cloud database:
    uv run python examples/demo_libsql_tenant.py verify --cloud

    # Live server you can open in a browser + copy-paste curl commands:
    uv run python examples/demo_libsql_tenant.py serve
    uv run python examples/demo_libsql_tenant.py serve --cloud

Credentials for ``--cloud`` (never committed; token is never printed):
    TURSO_DATABASE_URL / TURSO_AUTH_TOKEN
    or ASPARA_LIBSQL_URL / ASPARA_LIBSQL_AUTH_TOKEN

Note: polars / the libSQL native extension can segfault inside a restricted
sandbox. Run this outside the sandbox.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aspara.tenancy import (
    LibsqlTenant,
    configure_libsql_tenant_resolver,
    configure_tenant_resolver,
)

# Local demo files (fs tenant + local-libSQL artifacts). Cloud metrics do not land here;
# remote tenants do not store artifact bytes.
DEMO_DIR = Path(__file__).resolve().parent.parent / ".aspara_demo"
LIB_DIR = DEMO_DIR / "lib"
FS_BASE_DIR = DEMO_DIR / "fs"

TENANT_HEADER = "X-Aspara-Tenant"
CSRF = {"X-Requested-With": "XMLHttpRequest"}

PROJECT = "demo"
RUN = "run-1"

_MISSING_CLOUD_CREDS = """\
Missing Turso credentials. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN
(or ASPARA_LIBSQL_URL / ASPARA_LIBSQL_AUTH_TOKEN), e.g.:

  turso auth login
  turso db create aspara-demo --location aws-ap-northeast-1
  export TURSO_DATABASE_URL="$(turso db show aspara-demo --url)"
  export TURSO_AUTH_TOKEN="$(turso db tokens create aspara-demo)"

Then re-run:

  uv run python examples/demo_libsql_tenant.py verify --cloud
"""


def _cloud_creds() -> tuple[str, str]:
    """Read Turso URL + token from the environment. Never log the token."""
    url = os.environ.get("TURSO_DATABASE_URL") or os.environ.get("ASPARA_LIBSQL_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("ASPARA_LIBSQL_AUTH_TOKEN")
    if not url or not token:
        raise SystemExit(_MISSING_CLOUD_CREDS)
    return url, token


def _url_host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or url.split("@")[-1].split("/")[0]


def configure_tenants(*, cloud: bool = False) -> str | None:
    """Install the process-global resolvers for the demo's two tenants.

    ``lib`` resolves to a local libSQL file, or to Turso Cloud when ``cloud`` is
    true. Every other tenant falls back to a per-tenant filesystem directory
    (so ``fs`` -> ``{FS_BASE_DIR}/fs``).
    """
    if cloud:
        url, token = _cloud_creds()
        configure_libsql_tenant_resolver(
            lambda t, database=url, auth_token=token: (
                LibsqlTenant(database=database, auth_token=auth_token) if t == "lib" else None
            )
        )
        configure_tenant_resolver(lambda t: str(FS_BASE_DIR / t))
        return url
    configure_libsql_tenant_resolver(lambda t: LibsqlTenant(base_dir=str(LIB_DIR)) if t == "lib" else None)
    configure_tenant_resolver(lambda t: str(FS_BASE_DIR / t))
    return None


def _reset_demo_dir() -> None:
    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)


def _reset_remote_demo(url: str, token: str) -> None:
    """Wipe this demo's project rows on Turso so verify is repeatable."""
    from aspara.storage.metadata.libsql import PROJECT_META_DDL, RUN_META_DDL
    from aspara.storage.metrics.libsql import connect_libsql, ensure_metrics_schema

    conn = connect_libsql(database=url, auth_token=token)
    try:
        ensure_metrics_schema(conn)
        conn.execute(RUN_META_DDL)
        conn.execute(PROJECT_META_DDL)
        conn.execute("DELETE FROM metrics WHERE project = ?", (PROJECT,))
        conn.execute("DELETE FROM run_meta WHERE project = ?", (PROJECT,))
        conn.execute("DELETE FROM project_meta WHERE project = ?", (PROJECT,))
        conn.commit()
    finally:
        conn.close()


def _remote_metric_count(url: str, token: str) -> int:
    from aspara.storage.metrics.libsql import connect_libsql

    conn = connect_libsql(database=url, auth_token=token)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE project = ? AND run = ?",
            (PROJECT, RUN),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _values(payload: dict[str, Any], metric: str, run: str) -> list[float]:
    return payload["metrics"][metric][run]["values"]


def run_verify(*, cloud: bool) -> int:
    """Ingest for both tenants via the tracker, read back via the dashboard, prove isolation."""
    token = ""
    if cloud:
        url, token = _cloud_creds()
        print(f"== Cloud target: {_url_host(url)} ==")

    from fastapi.testclient import TestClient

    from aspara.server import app

    _reset_demo_dir()
    url = configure_tenants(cloud=cloud)
    if cloud:
        assert url is not None
        print("== Resetting demo project rows on Turso ==")
        _reset_remote_demo(url, token)

    client = TestClient(app)
    lib = {TENANT_HEADER: "lib"}
    fs = {TENANT_HEADER: "fs"}

    print("== 1. Create a run for each tenant (same project/run name) ==")
    created = client.post(
        f"/tracker/api/v1/projects/{PROJECT}/runs",
        json={"name": RUN, "tags": ["exp"], "notes": "hello", "config": {"lr": 0.01}},
        headers={**lib, **CSRF},
    )
    created.raise_for_status()
    print(f"   lib run_id: {created.json()['run_id']}")
    client.post(
        f"/tracker/api/v1/projects/{PROJECT}/runs",
        json={"name": RUN, "tags": ["fs-run"]},
        headers={**fs, **CSRF},
    ).raise_for_status()

    print("== 2. Log metrics over the tracker HTTP API (X-Aspara-Tenant header) ==")
    for step, loss in ((0, 1.0), (1, 0.5), (2, 0.25)):
        client.post(
            f"/tracker/api/v1/projects/{PROJECT}/runs/{RUN}/metrics",
            json={"metrics": {"loss": loss}, "step": step},
            headers={**lib, **CSRF},
        ).raise_for_status()
    for step, loss in ((0, 9.0), (1, 8.0)):
        client.post(
            f"/tracker/api/v1/projects/{PROJECT}/runs/{RUN}/metrics",
            json={"metrics": {"loss": loss}, "step": step},
            headers={**fs, **CSRF},
        ).raise_for_status()

    client.post(
        f"/tracker/api/v1/projects/{PROJECT}/runs/{RUN}/finish",
        json={"exit_code": 0},
        headers={**lib, **CSRF},
    ).raise_for_status()

    print("== 3. Read back from the dashboard for each tenant ==")
    lib_metrics = client.get(f"/api/projects/{PROJECT}/runs/metrics?runs={RUN}", headers=lib).json()
    fs_metrics = client.get(f"/api/projects/{PROJECT}/runs/metrics?runs={RUN}", headers=fs).json()
    lib_loss = _values(lib_metrics, "loss", RUN)
    fs_loss = _values(fs_metrics, "loss", RUN)
    print(f"   lib tenant loss: {lib_loss}")
    print(f"   fs  tenant loss: {fs_loss}")

    lib_meta = client.get(f"/api/projects/{PROJECT}/runs/{RUN}/metadata", headers=lib).json()
    print(f"   lib tenant metadata: tags={lib_meta['tags']} config={lib_meta['config']} is_finished={lib_meta['is_finished']}")

    lib_db = LIB_DIR / "aspara.db"
    fs_jsonl = FS_BASE_DIR / "fs" / PROJECT / f"{RUN}.jsonl"
    remote_rows = 0
    if cloud:
        assert url is not None
        remote_rows = _remote_metric_count(url, token)
        print("== 4. Prove the lib tenant landed on Turso (not a local file) ==")
        print(f"   Turso host:                  {_url_host(url)}")
        print(f"   remote metrics rows:         {remote_rows}")
        print(f"   local aspara.db absent:      {not lib_db.exists()}  ({lib_db})")
        print(f"   lib tenant has NO jsonl:     {not (LIB_DIR / PROJECT / f'{RUN}.jsonl').exists()}")
        print(f"   fs tenant jsonl exists:      {fs_jsonl.exists()}  ({fs_jsonl})")
        landed_ok = remote_rows == 3 and not lib_db.exists()
        result_ok = "RESULT: OK - libSQL tenant data is written to / read from Turso Cloud and isolated from the fs tenant."
    else:
        print("== 4. Prove where the bytes landed on disk ==")
        print(f"   libSQL DB exists:            {lib_db.exists()}  ({lib_db})")
        print(f"   lib tenant has NO jsonl:     {not (LIB_DIR / PROJECT / f'{RUN}.jsonl').exists()}")
        print(f"   fs tenant jsonl exists:      {fs_jsonl.exists()}  ({fs_jsonl})")
        landed_ok = lib_db.exists()
        result_ok = "RESULT: OK - libSQL tenant data is written to / read from its libSQL DB and isolated from the fs tenant."

    ok = (
        lib_loss == [1.0, 0.5, 0.25]
        and fs_loss == [9.0, 8.0]
        and lib_meta["tags"] == ["exp"]
        and lib_meta["config"] == {"lr": 0.01}
        and lib_meta["is_finished"] is True
        and landed_ok
        and not (LIB_DIR / PROJECT / f"{RUN}.jsonl").exists()
        and fs_jsonl.exists()
    )
    print()
    if ok:
        print(result_ok)
        return 0
    print("RESULT: FAILED - see values above.")
    return 1


def run_serve(host: str, port: int, reset: bool, *, cloud: bool) -> int:
    """Start the combined tracker+dashboard app with the demo tenants configured."""
    if cloud:
        _cloud_creds()

    import uvicorn

    from aspara.server import app

    if reset:
        _reset_demo_dir()
    else:
        DEMO_DIR.mkdir(parents=True, exist_ok=True)
    url = configure_tenants(cloud=cloud)

    base = f"http://{host}:{port}"
    backend = f"Turso Cloud ({_url_host(url)})" if cloud and url else f"local file ({LIB_DIR / 'aspara.db'})"
    print("=" * 70)
    print("Aspara multi-tenant libSQL demo server")
    print("=" * 70)
    print(f"lib tenant backend:        {backend}")
    print(f"Dashboard (lib / Turso):   {base}/?tenant=lib")
    print(f"Dashboard (fs tenant):     {base}/?tenant=fs")
    print(f"Tracker API base:          {base}/tracker/api/v1")
    print(f"Demo data dir:             {DEMO_DIR}")
    print("Open the ?tenant= URL in a browser; it sets a cookie so later clicks stay there.")
    print()
    print("Create a run, then log a metric for the libSQL tenant:")
    print(
        f"  curl -X POST {base}/tracker/api/v1/projects/{PROJECT}/runs \\\n"
        f'    -H "Content-Type: application/json" \\\n'
        f'    -H "X-Requested-With: XMLHttpRequest" \\\n'
        f'    -H "X-Aspara-Tenant: lib" \\\n'
        f'    -d \'{{"name": "{RUN}", "tags": ["cloud"]}}\''
    )
    print(
        f"  curl -X POST {base}/tracker/api/v1/projects/{PROJECT}/runs/{RUN}/metrics \\\n"
        f'    -H "Content-Type: application/json" \\\n'
        f'    -H "X-Requested-With: XMLHttpRequest" \\\n'
        f'    -H "X-Aspara-Tenant: lib" \\\n'
        f'    -d \'{{"metrics": {{"loss": 0.5}}, "step": 0}}\''
    )
    print()
    print("Read the metric back from the dashboard (same tenant):")
    print(f'  curl "{base}/api/projects/{PROJECT}/runs/metrics?runs={RUN}" -H "X-Aspara-Tenant: lib"')
    print()
    print("The 'fs' tenant is filesystem-backed and fully isolated (swap ?tenant= or the header).")
    print("=" * 70)

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def _add_cloud_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Use Turso Cloud for the lib tenant (TURSO_DATABASE_URL + TURSO_AUTH_TOKEN).",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="Ingest + read back via TestClient and print an isolation proof.")
    _add_cloud_flag(verify)

    serve = sub.add_parser("serve", help="Run a live tracker+dashboard server for manual testing.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8100)
    serve.add_argument("--reset", action="store_true", help="Wipe the local demo data dir before starting.")
    _add_cloud_flag(serve)

    args = parser.parse_args(argv)

    if args.command == "verify":
        return run_verify(cloud=args.cloud)
    if args.command == "serve":
        return run_serve(args.host, args.port, args.reset, cloud=args.cloud)
    return 1


if __name__ == "__main__":
    sys.exit(main())
