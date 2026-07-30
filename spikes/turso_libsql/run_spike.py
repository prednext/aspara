"""Spike runner: measure libSQL as a per-tenant metrics store, vs the current JSONL backend.

Questions this PoC answers for the multi-tenant SaaS direction:
1. Feasibility — does libSQL slot into the MetricsStorage interface? (see libsql_metrics_storage.py)
2. Cost — how big is one tenant's database on disk? (drives storage cost per tenant)
3. Speed — write throughput, and cold vs warm read latency (drives the "snappy dashboard" story)

Everything runs locally against files (no network, no Turso account), so it is a lower
bound / first-order proxy for the managed story. Run outside the sandbox (native extension).

Usage:
    uv run python spikes/turso_libsql/run_spike.py
    uv run python spikes/turso_libsql/run_spike.py --tenants 100 --metrics 5 --steps 1000
"""

from __future__ import annotations

import argparse
import os
import statistics
import tempfile
import time

from libsql_metrics_storage import LibsqlMetricsStorage

from aspara.storage import create_metrics_storage


def make_step(step: int, n_metrics: int) -> dict:
    base_ts = 1700000000000
    return {
        "timestamp": base_ts + step * 1000,
        "step": step,
        "metrics": {f"metric_{m}": step * 0.1 + m for m in range(n_metrics)},
    }


def dir_size_bytes(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def bench_libsql(root: str, n_tenants: int, n_metrics: int, n_steps: int) -> dict:
    db_dir = os.path.join(root, "libsql")
    os.makedirs(db_dir, exist_ok=True)

    # --- Write phase: one DB per tenant ---
    start = time.perf_counter()
    for t in range(n_tenants):
        store = LibsqlMetricsStorage(os.path.join(db_dir, f"tenant_{t}.db"))
        for s in range(n_steps):
            store.save(make_step(s, n_metrics))
        store.close()
    write_s = time.perf_counter() - start

    total_rows = n_tenants * n_steps * n_metrics
    size = dir_size_bytes(db_dir)

    # --- Read phase: cold (fresh connection) vs warm (same connection) ---
    sample = min(n_tenants, 20)
    cold, warm = [], []
    for t in range(sample):
        db_path = os.path.join(db_dir, f"tenant_{t}.db")
        c0 = time.perf_counter()
        store = LibsqlMetricsStorage(db_path)  # cold open
        _ = store.load()
        cold.append((time.perf_counter() - c0) * 1000)
        w0 = time.perf_counter()
        _ = store.load()  # warm
        warm.append((time.perf_counter() - w0) * 1000)
        store.close()

    return {
        "backend": "libSQL",
        "write_s": write_s,
        "writes_per_s": total_rows / write_s,
        "avg_db_kb": size / n_tenants / 1024,
        "cold_ms": statistics.median(cold),
        "warm_ms": statistics.median(warm),
    }


def bench_jsonl(root: str, n_tenants: int, n_metrics: int, n_steps: int) -> dict:
    base_dir = os.path.join(root, "jsonl")
    os.makedirs(base_dir, exist_ok=True)

    start = time.perf_counter()
    for t in range(n_tenants):
        store = create_metrics_storage("jsonl", base_dir=base_dir, project_name=f"tenant_{t}", run_name="run")
        for s in range(n_steps):
            store.save(make_step(s, n_metrics))
        store.close()
    write_s = time.perf_counter() - start

    total_rows = n_tenants * n_steps * n_metrics
    size = dir_size_bytes(base_dir)

    sample = min(n_tenants, 20)
    cold = []
    for t in range(sample):
        store = create_metrics_storage("jsonl", base_dir=base_dir, project_name=f"tenant_{t}", run_name="run")
        c0 = time.perf_counter()
        _ = store.load()
        cold.append((time.perf_counter() - c0) * 1000)
        store.close()

    return {
        "backend": "JSONL (current)",
        "write_s": write_s,
        "writes_per_s": total_rows / write_s,
        "avg_db_kb": size / n_tenants / 1024,
        "cold_ms": statistics.median(cold),
        "warm_ms": float("nan"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="libSQL per-tenant storage spike")
    parser.add_argument("--tenants", type=int, default=100)
    parser.add_argument("--metrics", type=int, default=5)
    parser.add_argument("--steps", type=int, default=1000)
    args = parser.parse_args()

    print(f"Tenants={args.tenants}, metrics={args.metrics}, steps={args.steps} ({args.tenants * args.metrics * args.steps:,} metric rows total)\n")

    with tempfile.TemporaryDirectory() as root:
        results = [
            bench_libsql(root, args.tenants, args.metrics, args.steps),
            bench_jsonl(root, args.tenants, args.metrics, args.steps),
        ]

    header = f"  {'Backend':<16}  {'Write(s)':>9}  {'Rows/sec':>12}  {'Avg/tenant':>11}  {'Cold read':>10}  {'Warm read':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in results:
        warm = "   n/a" if r["warm_ms"] != r["warm_ms"] else f"{r['warm_ms']:.2f}ms"  # nan check
        print(f"  {r['backend']:<16}  {r['write_s']:>8.2f}s  {r['writes_per_s']:>12,.0f}  {r['avg_db_kb']:>8.1f}KB  {r['cold_ms']:>8.2f}ms  {warm:>10}")


if __name__ == "__main__":
    main()
