"""Benchmark for the /api/projects/{project}/runs/metrics endpoint.

Measures response time and size for both JSON and msgpack formats.
Uses httpx AsyncClient with ASGITransport so no server process is needed.

Usage:
    uv run python benchmarks/bench_metrics_api.py
    uv run python benchmarks/bench_metrics_api.py --runs 10 --metrics 20 --steps 2000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path

import httpx
import msgpack

from aspara.dashboard.dependencies import configure_data_dir
from aspara.dashboard.main import app


def create_test_data(data_dir: Path, n_runs: int, n_metrics: int, n_steps: int) -> str:
    """Create test JSONL data files.

    Returns:
        Project name used for the test data.
    """
    project = "bench_project"
    project_dir = data_dir / project
    project_dir.mkdir(parents=True, exist_ok=True)

    base_ts = 1700000000000  # Fixed base timestamp in ms

    for r in range(n_runs):
        run_name = f"run_{r}"
        run_file = project_dir / f"{run_name}.jsonl"
        meta_file = project_dir / f"{run_name}.meta.json"

        # Write metrics JSONL
        with run_file.open("w") as f:
            for s in range(n_steps):
                entry = {
                    "timestamp": base_ts + s * 1000,
                    "step": s,
                    "metrics": {f"metric_{m}": s * 0.1 + m for m in range(n_metrics)},
                }
                f.write(json.dumps(entry) + "\n")

        # Write minimal metadata
        meta = {
            "run_id": run_name,
            "tags": [],
            "notes": "",
            "params": {},
            "config": {},
            "artifacts": [],
            "summary": {},
            "is_finished": True,
            "exit_code": 0,
            "start_time": base_ts,
            "finish_time": base_ts + n_steps * 1000,
        }
        meta_file.write_text(json.dumps(meta))

    return project


async def bench_endpoint(
    client: httpx.AsyncClient,
    url: str,
    n_warmup: int = 3,
    n_iterations: int = 20,
) -> tuple[list[float], int]:
    """Benchmark a single endpoint.

    Returns:
        (list of response times in ms, response size in bytes)
    """
    # Warmup
    for _ in range(n_warmup):
        resp = await client.get(url, headers={"X-Requested-With": "benchmark"})
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text[:200]}"

    # Measure
    times: list[float] = []
    size = 0
    for _ in range(n_iterations):
        start = time.perf_counter()
        resp = await client.get(url, headers={"X-Requested-With": "benchmark"})
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
        size = len(resp.content)

    return times, size


def bench_serialization_only(data: dict, n_iterations: int = 100) -> dict[str, list[float]]:
    """Benchmark raw serialization of the metrics dict.

    Returns:
        Dict mapping format name to list of times in ms.
    """
    results: dict[str, list[float]] = {}

    # JSON via stdlib
    json_times: list[float] = []
    for _ in range(n_iterations):
        start = time.perf_counter()
        json.dumps(data)
        elapsed = (time.perf_counter() - start) * 1000
        json_times.append(elapsed)
    results["json (stdlib)"] = json_times

    # msgpack
    msgpack_times: list[float] = []
    for _ in range(n_iterations):
        start = time.perf_counter()
        msgpack.packb(data, use_single_float=True)
        elapsed = (time.perf_counter() - start) * 1000
        msgpack_times.append(elapsed)
    results["msgpack"] = msgpack_times

    return results


def print_stats(label: str, times: list[float], size_kb: float | None = None) -> None:
    """Print timing statistics."""
    median = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    mean = statistics.mean(times)
    size_str = f"  size={size_kb:.1f}KB" if size_kb is not None else ""
    print(f"  {label:30s}  median={median:7.2f}ms  p95={p95:7.2f}ms  mean={mean:7.2f}ms{size_str}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark metrics API endpoint")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs (default: 5)")
    parser.add_argument("--metrics", type=int, default=10, help="Number of metrics per run (default: 10)")
    parser.add_argument("--steps", type=int, default=1000, help="Number of steps per metric (default: 1000)")
    parser.add_argument("--iterations", type=int, default=20, help="Number of benchmark iterations (default: 20)")
    args = parser.parse_args()

    print(f"Benchmark config: {args.runs} runs x {args.metrics} metrics x {args.steps} steps")
    print(f"Iterations: {args.iterations}")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        project = create_test_data(data_dir, args.runs, args.metrics, args.steps)
        configure_data_dir(str(data_dir))

        try:
            run_names = ",".join(f"run_{r}" for r in range(args.runs))

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                url_json = f"/api/projects/{project}/runs/metrics?runs={run_names}&format=json"
                url_msgpack = f"/api/projects/{project}/runs/metrics?runs={run_names}&format=msgpack"

                print("--- Endpoint response time ---")
                json_times, json_size = await bench_endpoint(client, url_json, n_iterations=args.iterations)
                msgpack_times, msgpack_size = await bench_endpoint(client, url_msgpack, n_iterations=args.iterations)

                print_stats("JSON (Pydantic+Rust)", json_times, json_size / 1024)
                print_stats("msgpack", msgpack_times, msgpack_size / 1024)

                json_median = statistics.median(json_times)
                msgpack_median = statistics.median(msgpack_times)
                print(f"\n  JSON/msgpack ratio: {json_median / msgpack_median:.2f}x")

            # Serialization-only benchmark
            print("\n--- Serialization only (raw dict -> bytes) ---")
            # Build a representative data dict
            sample_data: dict = {"project": project, "metrics": {}}
            for m in range(args.metrics):
                metric_dict: dict = {}
                for r in range(args.runs):
                    metric_dict[f"run_{r}"] = {
                        "steps": list(range(args.steps)),
                        "values": [i * 0.1 for i in range(args.steps)],
                        "timestamps": [1700000000000 + i * 1000 for i in range(args.steps)],
                    }
                sample_data["metrics"][f"metric_{m}"] = metric_dict

            ser_results = bench_serialization_only(sample_data, n_iterations=args.iterations)
            for label, times in ser_results.items():
                size = len(json.dumps(sample_data).encode()) / 1024 if "json" in label else len(msgpack.packb(sample_data, use_single_float=True)) / 1024
                print_stats(label, times, size)
        finally:
            configure_data_dir(None)


if __name__ == "__main__":
    asyncio.run(main())
