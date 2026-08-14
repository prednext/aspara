# Design memo: tenant provisioning & region placement (SaaS)

**Status:** design memo (branch `spike/turso-libsql`). No production code yet.
**Scope:** how a tenant maps to a Turso/libSQL database, how that database is provisioned and
placed in a region, and how the running app resolves a request → tenant → database. Builds directly
on [`FINDINGS.md`](./FINDINGS.md) (Turso PoC). Non-goals here: billing, quotas, backup/DR details.

Decisions already made (from the roadmap / FINDINGS):

- **Tenant = user** (start with individual accounts).
- **DB = Turso/libSQL, one database per tenant.**
- **Writes are remote-only for now** (embedded replica deferred; see FINDINGS).
- **All code is OSS / self-hostable.**

---

## 1. Where we're starting from (grounded in the current code)

aspara today is single-user and single-directory. The relevant facts this design must respect:

| Concern | Current behavior | Reference |
| --- | --- | --- |
| Data root | One `data_dir` per process: `ASPARA_DATA_DIR` → `XDG_DATA_HOME/aspara` → `~/.local/share/aspara` | `src/aspara/config.py` `get_data_dir()` |
| Layout | `{data_dir}/{project}/{run}.jsonl` (+ `.meta.json`, polars WAL/parquet, `artifacts/`) | `storage/metrics/jsonl.py`, `storage/metadata/*` |
| Storage abstraction | `MetricsStorage` bound to **(base_dir, project, run)**; backends `jsonl`\|`polars` via `ASPARA_STORAGE_BACKEND` | `storage/metrics/__init__.py` `create_metrics_storage()` |
| Dashboard data source | One `data_dir` **fixed at startup**; project/run come from the URL path `/projects/{project}/runs/{run}` | `dashboard/dependencies.py` `_get_catalogs()` |
| Remote writes | Client `RemoteRun` → Tracker API, which itself calls `get_data_dir()` + `create_metrics_storage()` | `tracker/router.py` |
| Auth / tenancy | **None.** CSRF header + optional `ASPARA_READ_ONLY` only. No user/account/tenant concept anywhere in `src/` | `cli.py` `_warn_wildcard_host`, `dashboard/routes/api_routes.py` |

**Implication:** the whole app resolves data through a single process-global `data_dir` and a
storage factory keyed by `(base_dir, project, run)`. Multi-tenancy is fundamentally a matter of
inserting a **tenant dimension in front of that factory** and carrying a tenant id through each
request — not of rewriting storage or the dashboard.

---

## 2. Tenancy model

```
account (user)  ──1:1──▶  tenant  ──1:1──▶  Turso database
                                   └── contains many projects, each with many runs
```

- **One tenant = one Turso database.** The PoC showed this is cheap (~10k tenants ≈ 2.7 GB, inside
  the free tier) and gives hard isolation (a query can only ever touch one tenant's DB).
- **Projects and runs live *inside* the tenant DB.** They stay logical (columns / a table naming
  scheme), not separate databases — otherwise DB count explodes and cross-project dashboard queries
  get awkward. See §5 for the intra-DB schema options.
- Keep the existing `default` project behavior (`_base_run.py`: `project or "default"`) so a fresh
  tenant works with zero configuration.

### Mapping to the existing abstraction

The cleanest insertion point is the storage factory. Conceptually:

```
create_metrics_storage(backend, base_dir, project, run)          # today
create_metrics_storage(backend, tenant, project, run)            # SaaS: tenant → DB URL+token
```

For a libSQL backend, `(project, run)` become row/column values inside the tenant DB instead of a
file path. `base_dir` (a filesystem path) is replaced by a **tenant handle** that resolves to a
`(database_url, auth_token)` pair.

---

## 3. Provisioning: creating and retiring a tenant DB

### Turso building blocks (from the spike)

- Databases belong to a **group**, and **the group fixes the region(s)** — we hit exactly this:
  `turso db create ... --location <id>` fails unless the location is part of the group.
- Location ids are full names on this plan: `aws-ap-northeast-1` (Tokyo), `aws-eu-west-1` (Ireland),
  `aws-us-east-1`, etc. (`turso db locations`).
- Auth: a **group token** was the reliable way to authenticate against a freshly created
  group/DB (a per-DB token gave `auth role not found` right after creation).

### Lifecycle

| Event | Action |
| --- | --- |
| Sign-up | Create tenant DB in the group for the user's chosen/nearest region; store `tenant_id → (db_name, group/region, url)`; mint an auth token. |
| First write/read | Lazily create the schema (`CREATE TABLE IF NOT EXISTS`, as the PoC does) — no migration step needed for a new DB. |
| Token rotation | Prefer short-lived tokens minted from a group/parent token held server-side; never store long-lived per-tenant tokens in the clear. |
| Delete / export | `turso db destroy` after an export; keep a soft-delete window. |

### Provisioning options (control plane)

1. **Turso Platform API / `turso` CLI** invoked by our control plane at sign-up (programmatic
   `db create` + `tokens create`). Simple; ties us to Turso Cloud.
2. **Pre-created pool** of blank DBs per region, assigned on sign-up to hide creation latency.
3. **Self-host path (OSS):** point a tenant at any libSQL/sqld URL. Since all code is OSS, the
   tenant→DB resolver must accept an arbitrary `(url, token)` and not assume Turso Cloud.

> Design the resolver around `(database_url, auth_token)`, and treat "Turso Cloud" as one
> implementation of "where do I get those?". That keeps self-host first-class.

---

## 4. Region placement (this is a product decision, not a detail)

The PoC made region placement the single biggest lever on perceived latency:

| Measurement | Tokyo (`aws-ap-northeast-1`) | Ireland (`aws-eu-west-1`) |
| --- | --- | --- |
| cold connect + `SELECT 1` | **309 ms** | **1,436–1,792 ms** |
| remote write (per statement) | ~40 ms | ~220 ms (1k-row write effectively hangs) |

Guidance:

- **Place each tenant's DB in a region near that tenant's users.** Latency is dominated by RTT, and
  remote-only writes are per-statement round trips, so a far region is not just "slower" — it can be
  unusable for bulk writes.
- **Choose the region at sign-up** (explicit picker, defaulting to geo/IP inference), because a
  Turso group is pinned to region(s) and moving later is a data migration.
- **Start with one or two default regions** (e.g. Tokyo + a US/EU option) rather than all six; add
  regions on demand. Each region needs its own group.
- Keep `tenant → region` in the control-plane record so we can report/operate on it and so a future
  "migrate region" tool has a source of truth.

Batching note (cheap mitigation before anything fancy): wrap a client's per-step metrics into **one
transaction per log call** so many inserts cost one round trip. Whether an explicit `BEGIN…COMMIT`
collapses remote inserts to a single trip is still unverified (see FINDINGS) and should be confirmed
before sizing the write path.

---

## 5. Intra-tenant schema (projects/runs inside one DB)

Today project/run are directory/file names. Inside a single tenant DB, options:

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| **A. Columns (recommended)** | `metrics(project, run, ts, step, name, value)` + index on `(project, run, name, step)` | one schema, easy cross-project queries, simple provisioning | wide index; project/run repeat per row |
| B. Table-per-run | `run_<hash>(ts, step, name, value)` | tight per-run scans | table sprawl; catalog/list becomes metadata bookkeeping |
| C. Separate DB per project | many DBs per tenant | strong project isolation | DB-count blowup; breaks "compare across projects" |

Recommendation: **Option A**. It preserves the current catalog model (list projects/runs) as
`SELECT DISTINCT`, and matches the PoC's long-format schema with `project`/`run` added.

---

## 6. Request → tenant → database resolution

What must be added to the app (all net-new, no rewrite of storage/dashboard internals):

1. **Tenant identity on each request.** Options: subdomain (`{tenant}.aspara.app`), a JWT claim, or
   a header. This is the same slot where authN/authZ goes (today there is none).
2. **Tenant context middleware.** Resolve tenant id → put it on `Request.state` (there is currently
   no such middleware; only `SecurityHeadersMiddleware` exists). Every catalog/storage dependency
   then reads tenant from context instead of the process-global `data_dir`.
3. **Tenant-scoped storage/catalog factory.** Replace the single `data_dir` in
   `dashboard/dependencies.py::_get_catalogs()` and in `create_metrics_storage()` call sites with a
   tenant-scoped resolver returning `(database_url, auth_token)`.
4. **Connection management.** Remote-only means a fresh connection is ~300 ms cold vs ~33 ms warm —
   so **reuse warm connections per tenant** (pool / LRU keyed by tenant), don't reconnect per query.
5. **Secrets.** Auth tokens are secrets: store encrypted server-side, mint short-lived tokens, never
   log them, never commit them (the spike scripts already read creds from env only).

---

## 7. Smallest first slice (thin vertical)

Before building the full control plane, prove the request path end-to-end for a single hard-coded
tenant:

1. Promote the spike's `LibsqlMetricsStorage` into a real backend option
   (`ASPARA_STORAGE_BACKEND=libsql`) that connects remote-only to `(url, token)` from env, with
   `project`/`run` as columns (Option A).
2. Add a `tenant_id` on `Request.state` from a header, defaulting to a single dev tenant.
3. Make `_get_catalogs()` and the storage factory read `tenant_id` and resolve to a per-tenant
   `(url, token)` from a tiny in-memory map.
4. Run two tenants against two Turso DBs and confirm complete isolation with an automated test
   (tenant A can never see tenant B's projects/runs).

That single slice de-risks the "insert a tenant dimension in front of the factory" thesis without
committing to provisioning, auth, or billing.

---

## Open questions

- Does an explicit transaction batch remote inserts into one round trip? (sizes the write path)
- Group-per-region vs multi-region group — cost and operational trade-offs at low tenant counts.
- Token model: per-tenant tokens vs a server-held parent token minting short-lived ones.
- Self-host story for the tenant→DB resolver (arbitrary libSQL URL, not just Turso Cloud).
