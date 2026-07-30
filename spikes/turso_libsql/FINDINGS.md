# Spike: libSQL (Turso) as a per-tenant metrics store

**Status:** proof-of-concept (branch `spike/turso-libsql`). Not production code.
**Goal:** validate whether libSQL — the SQLite-compatible engine behind Turso — can back a
multi-tenant SaaS version of aspara using a "one database per tenant" model, and get first-order
numbers on cost (disk size) and latency.

## What was built

- `libsql_metrics_storage.py` — a `LibsqlMetricsStorage` that implements aspara's existing
  `MetricsStorage` interface (`save` / `load`) against a single libSQL database file per tenant.
  It dropped into the abstraction with no changes to core code.
- `run_spike.py` — a runner that writes N tenants × M metrics × S steps and measures write
  throughput, on-disk size per tenant, and cold vs warm read latency, comparing libSQL against
  the current JSONL backend.

## Results

Local files only (no network / no Turso Cloud). Apple Silicon, Python 3.12, libsql 0.1.11.
100 tenants × 5 metrics × 1,000 steps = 500,000 metric rows.

| Backend        | Write  | Rows/sec | Avg/tenant | Cold read | Warm read |
| -------------- | -----: | -------: | ---------: | --------: | --------: |
| libSQL         | 1.32 s |  378,330 |    280 KB  |   3.11 ms |   3.01 ms |
| JSONL (current)| 4.89 s |  102,173 |    163 KB  |   1.08 ms |     n/a   |

## Interpretation

- **Feasibility: confirmed.** libSQL fits the `MetricsStorage` interface cleanly, and
  one-DB-per-tenant is trivial to provision (just a file path). This is the shape a Turso-backed
  SaaS would take.
- **Write throughput: libSQL ~3.7× faster** than JSONL (batched commit at close).
- **Disk cost: libSQL is ~1.7× larger** per tenant here (280 KB vs 163 KB). Two levers explain it
  and can shrink it: (1) we add a `(name, step)` index; (2) the schema is long-format so the
  metric name repeats on every row. A wide or blob/compressed schema, or dropping the index, would
  narrow the gap. Note: aspara also ships a `polars` (parquet) backend that would be far smaller —
  we only compared against `jsonl` here.
- **Read latency: sub-5 ms locally** for both; libSQL is a bit slower (long-format + `ORDER BY`).
  Well within interactive limits.

### Cost sanity check (multi-tenant)
At ~280 KB per tenant for this volume, 10,000 tenants ≈ 2.7 GB — comfortably inside Turso's
current 5 GB free tier. The "cheap multi-tenant" thesis holds for small per-tenant volumes; the
schema levers above matter as volume grows.

## Cloud results (real Turso)

Measured against real Turso databases via `run_cloud_spike.py`. Client in Japan.
libSQL exposes two connection modes; we measured both.

**Tokyo primary** (`aws-ap-northeast-1`, near the client), 3 steps × 5 metrics = 15 rows:

| Operation (Remote-only)            |  Time   | Notes                                  |
| ---------------------------------- | ------: | -------------------------------------- |
| cold connect + `SELECT 1`          | 309 ms  | TLS handshake + auth + first query     |
| `CREATE TABLE`                     |  76 ms  | one network round trip                 |
| `INSERT` 1 row (probe)             |  78 ms  | **one round trip per statement**       |
| `INSERT` 14 rows (`executemany`)   | 565 ms  | ≈ 40 ms/row — **not batched**          |
| warm read (open connection)        |  33 ms (median) | one RTT                        |
| cold read (fresh connection)       | 193 ms (median) | handshake every time           |

| Operation (Embedded replica)       |  Time   | Notes                                  |
| ---------------------------------- | ------: | -------------------------------------- |
| connect                            | 385 ms  |                                        |
| initial `sync()`                   | 267 ms  | pull DB to local file                  |
| `sync()` after 15-row write        |  98 ms  | incremental                            |
| local read (after sync)            | **0.06 ms** (median) | SQLite local speed        |

**Far region contrast** (`aws-eu-west-1`, Ireland): cold connect **1,436–1,792 ms**, and a
1,000-row remote-only write never finished in practice (≈ 220 ms/round trip × 1,000 ≈ minutes).

## Interpretation (cloud)

- **Remote-only is round-trip-bound and unfit for the write path.** Every statement is a network
  round trip (~40 ms same-region, ~220 ms far). aspara logs thousands of steps per run, so
  per-step remote writes would take minutes — and are catastrophic across regions. `executemany`
  does not batch this away.
- **Embedded replica is the answer.** Reads are served from a local synced file at **0.06 ms**
  (on par with the local JSONL/SQLite baseline), while `sync()` pushes/pulls in the background at
  ~100–270 ms. This preserves aspara's local-first speed *and* gets cloud durability + multi-device.
- **Region placement dominates perceived latency** (309 ms vs ~1.6 s cold connect). Tenant DBs must
  be provisioned near their users; this is a first-class product/ops decision, not a detail.

### Architecture implication for aspara SaaS
Use the **embedded-replica** model, not remote-only: the client/server writes locally and syncs to
Turso in the background (batched, ideally inside explicit transactions to amortize round trips);
dashboards read from the local replica. Turso remains the durable, per-tenant source of truth.

## Caveats / what this does NOT prove

- Durability model here is batched (commit on close). Per-step `commit()` would be slower.
- Single-writer assumption; concurrent writers per tenant not tested.
- Cloud runs used tiny payloads (15 rows) to isolate latency; sustained write throughput and
  large-history sync time under the embedded-replica model still need a dedicated run.
- Whether an explicit `BEGIN … COMMIT` transaction batches remote inserts into one round trip was
  not confirmed (the `executemany` path did not) — worth verifying before sizing the write path.

## Recommended next steps

1. ~~Cloud spike~~ **done** (above): embedded replica is the model; remote-only is unfit for writes.
2. **Prototype an embedded-replica storage backend:** local write + background `sync()`, and measure
   sustained write throughput and large-history sync time (not just 15-row latency).
3. **Confirm transaction batching:** does an explicit `BEGIN … COMMIT` collapse many inserts into
   one round trip? Sizes the write path.
4. **Schema tuning:** compare long-format vs wide vs compressed-blob on size, and index on/off.
5. **Compare against the `polars` backend**, not just `jsonl`, for a fair disk-size baseline.
6. **Provisioning model:** tenant → DB mapping, region placement near users, connection warm-keeping.

## Reproduce

Local (no network):

```bash
uv run python spikes/turso_libsql/run_spike.py --tenants 100 --metrics 5 --steps 1000
```

Cloud (needs a Turso DB; credentials via env, never committed):

```bash
export TURSO_DATABASE_URL="$(turso db show <db> --url)"
export TURSO_AUTH_TOKEN="$(turso db tokens create <db>)"
uv run python spikes/turso_libsql/run_cloud_spike.py --metrics 5 --steps 20 --read-iters 15
```

Note: place the Turso DB in a region near you (`turso db locations`); a far region turns cold
connects into ~1.5 s and makes remote-only writes unusable.
