"""Cloud spike: measure real Turso latency (remote-only vs embedded replica).

The local spike (run_spike.py) proved feasibility and disk cost but could NOT measure the
thing that decides dashboard feel: network round-trip and cold vs warm connection behavior.
This script does that against a REAL Turso database.

It measures two connection modes libSQL supports:
  A) Remote-only     — every query hits Turso over the network (RTT-bound).
  B) Embedded replica — a local file synced from Turso; reads are local after sync().

Credentials are read from environment variables (never hard-coded / committed):
    TURSO_DATABASE_URL   e.g. libsql://<db>-<org>.turso.io
    TURSO_AUTH_TOKEN     a database token (turso db tokens create <db>)

Run outside the sandbox (native extension + network):
    TURSO_DATABASE_URL=... TURSO_AUTH_TOKEN=... uv run python spikes/turso_libsql/run_cloud_spike.py
    ... --metrics 5 --steps 200 --read-iters 15
"""

from __future__ import annotations

import argparse
import functools
import os
import statistics
import tempfile
import time

import libsql  # type: ignore[import-not-found]

# Flush every line immediately so a slow remote op looks slow, not "hung".
print = functools.partial(print, flush=True)  # noqa: A001

_CREATE = "CREATE TABLE IF NOT EXISTS spike_metrics (ts INTEGER, step INTEGER, name TEXT, value REAL)"


def _phase(label: str):
    """Context-manager-ish timer that announces start and prints elapsed on exit."""

    class _T:
        def __enter__(self):
            print(f"  -> {label} ...")
            self.t0 = time.perf_counter()
            return self

        def __exit__(self, *exc):
            print(f"     {label} done in {(time.perf_counter() - self.t0) * 1000:8.2f}ms")
            return False

    return _T()


def make_rows(n_steps: int, n_metrics: int) -> list[tuple[int, int, str, float]]:
    base_ts = 1700000000000
    rows: list[tuple[int, int, str, float]] = []
    for s in range(n_steps):
        for m in range(n_metrics):
            rows.append((base_ts + s * 1000, s, f"metric_{m}", s * 0.1 + m))
    return rows


def timed_reads(conn, n_iters: int) -> list[float]:
    times: list[float] = []
    for _ in range(n_iters):
        t0 = time.perf_counter()
        conn.execute("SELECT ts, step, name, value FROM spike_metrics ORDER BY step").fetchall()
        times.append((time.perf_counter() - t0) * 1000)
    return times


def summarize(name: str, times: list[float]) -> str:
    med = statistics.median(times)
    p95 = sorted(times)[min(len(times) - 1, int(len(times) * 0.95))]
    return f"  {name:<34}  median={med:8.2f}ms  p95={p95:8.2f}ms"


def bench_remote(url: str, token: str, rows: list[tuple], read_iters: int) -> None:
    print("A) Remote-only (every query over the network)")

    # Cold connect + trivial round trip
    c0 = time.perf_counter()
    conn = libsql.connect(url, auth_token=token)
    conn.execute("SELECT 1").fetchone()
    print(f"  cold connect + SELECT 1            {(time.perf_counter() - c0) * 1000:8.2f}ms")

    with _phase("CREATE TABLE"):
        conn.execute(_CREATE)
        conn.commit()
    with _phase("DELETE (reset)"):
        conn.execute("DELETE FROM spike_metrics")
        conn.commit()

    # Time a single INSERT first to expose per-statement round-trip cost.
    with _phase("INSERT 1 row (probe round-trip)"):
        conn.execute(
            "INSERT INTO spike_metrics (ts, step, name, value) VALUES (?, ?, ?, ?)", rows[0]
        )
        conn.commit()
    with _phase(f"INSERT {len(rows) - 1:,} more rows (executemany)"):
        conn.executemany(
            "INSERT INTO spike_metrics (ts, step, name, value) VALUES (?, ?, ?, ?)", rows[1:]
        )
        conn.commit()

    # Warm reads on the open connection
    print(summarize("warm read (open connection)", timed_reads(conn, read_iters)))
    conn.close()

    # Cold read: brand-new connection each time
    cold: list[float] = []
    for _ in range(min(read_iters, 8)):
        t0 = time.perf_counter()
        c = libsql.connect(url, auth_token=token)
        c.execute("SELECT ts, step, name, value FROM spike_metrics ORDER BY step").fetchall()
        cold.append((time.perf_counter() - t0) * 1000)
        c.close()
    print(summarize("cold read (fresh connection)", cold))


def bench_embedded_replica(url: str, token: str, rows: list[tuple], read_iters: int) -> None:
    print("\nB) Embedded replica (local file synced from Turso)")
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, "replica.db")

        c0 = time.perf_counter()
        conn = libsql.connect(local, sync_url=url, auth_token=token)
        connect_ms = (time.perf_counter() - c0) * 1000

        s0 = time.perf_counter()
        conn.sync()
        sync_ms = (time.perf_counter() - s0) * 1000
        print(f"  connect                            {connect_ms:8.2f}ms")
        print(f"  initial sync()                     {sync_ms:8.2f}ms")

        # Ensure data exists (write goes to remote, then sync back)
        conn.execute(_CREATE)
        conn.execute("DELETE FROM spike_metrics")
        conn.executemany("INSERT INTO spike_metrics (ts, step, name, value) VALUES (?, ?, ?, ?)", rows)
        conn.commit()
        s1 = time.perf_counter()
        conn.sync()
        print(f"  sync() after {len(rows):>6,} row write   {(time.perf_counter() - s1) * 1000:8.2f}ms")

        # Reads are now local
        print(summarize("local read (after sync)", timed_reads(conn, read_iters)))
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Turso cloud latency spike")
    parser.add_argument("--metrics", type=int, default=5)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--read-iters", type=int, default=15)
    parser.add_argument("--skip-replica", action="store_true", help="Only run the remote-only mode")
    args = parser.parse_args()

    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if not url or not token:
        print("Missing credentials. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN, e.g.:\n")
        print("  turso db create aspara-spike")
        print("  turso db show aspara-spike --url          # -> TURSO_DATABASE_URL")
        print("  turso db tokens create aspara-spike       # -> TURSO_AUTH_TOKEN\n")
        print("Then re-run:")
        print("  TURSO_DATABASE_URL=... TURSO_AUTH_TOKEN=... uv run python spikes/turso_libsql/run_cloud_spike.py")
        raise SystemExit(1)

    rows = make_rows(args.steps, args.metrics)
    print(f"Turso URL: {url.split('@')[-1]}")
    print(f"Payload: {args.steps} steps x {args.metrics} metrics = {len(rows):,} rows, read x{args.read_iters}\n")

    bench_remote(url, token, rows, args.read_iters)
    if not args.skip_replica:
        try:
            bench_embedded_replica(url, token, rows, args.read_iters)
        except Exception as e:  # noqa: BLE001 - spike: report and continue
            print(f"\nB) Embedded replica FAILED: {type(e).__name__}: {e}")
            print("  (Some libsql builds/plans restrict embedded replicas — note and continue.)")


if __name__ == "__main__":
    main()
