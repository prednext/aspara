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

## Caveats / what this does NOT prove

- **Local file ≠ Turso Cloud.** No network RTT, no replication, no embedded-replica sync. The
  Turso research flagged cold-start / warm-connection behavior as decisive for dashboard feel —
  that is exactly what local files cannot measure and is the next thing to test.
- Durability model here is batched (commit on close). Per-step `commit()` would be slower.
- Single-writer assumption; concurrent writers per tenant not tested.

## Recommended next steps

1. **Cloud spike (needs Turso account + network):** repeat read latency against a real Turso DB,
   with and without an embedded replica, and measure cold vs warm connection.
2. **Schema tuning:** compare long-format vs wide vs compressed-blob on size, and index on/off.
3. **Compare against the `polars` backend**, not just `jsonl`, for a fair disk-size baseline.
4. **Provisioning model:** prototype tenant → DB mapping + connection pooling / warm-keeping.

## Reproduce

```bash
uv run python spikes/turso_libsql/run_spike.py --tenants 100 --metrics 5 --steps 1000
```
