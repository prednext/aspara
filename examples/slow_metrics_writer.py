"""
Simple slow metrics writer for testing SSE real-time updates.

This is a simpler version that's easy to customize.

Usage:
    # Terminal 1: Start dashboard
    aspara dashboard

    # Terminal 2: Run this script
    uv run python examples/slow_metrics_writer.py

    # Terminal 3 (optional): Run again with different run name
    uv run python examples/slow_metrics_writer.py --run experiment_2

    # Open browser and watch metrics update in real-time!
"""

import argparse
import math
import random
import time
from datetime import datetime

from aspara import Run


def main():
    parser = argparse.ArgumentParser(description="Slow metrics writer for SSE testing")
    parser.add_argument("--project", default="sse_test", help="Project name")
    parser.add_argument("--run", default="experiment_1", help="Run name")
    parser.add_argument("--steps", type=int, default=30, help="Number of steps")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between steps (seconds)")
    args = parser.parse_args()

    # Random parameters for this run
    run_seed = hash(args.run) % 1000
    random.seed(run_seed)

    loss_base = 1.2 + random.uniform(-0.2, 0.2)
    acc_base = 0.3 + random.uniform(-0.1, 0.1)
    noise_level = 0.015 + random.uniform(0, 0.01)

    # Create run
    run = Run(
        project=args.project,
        name=args.run,
        tags=["sse", "test", "realtime"],
        notes="Testing SSE real-time updates",
    )

    print(f"🚀 Writing metrics to {args.project}/{args.run}")
    print(f"   Steps: {args.steps}, Delay: {args.delay}s")
    print(f"   Base Loss: {loss_base:.3f}, Base Acc: {acc_base:.3f}")
    print("   Open http://localhost:3141 to watch in real-time!\n")

    # Write metrics gradually
    for step in range(args.steps):
        # Add noise (periodic + random)
        noise = noise_level * (math.sin(step * 0.4) * 0.5 + random.gauss(0, 0.5))

        # Simulate training metrics with noise
        loss = max(0.01, (loss_base / (step + 1)) + noise)
        accuracy = min(0.99, acc_base + (0.6 * (1.0 - 1.0 / (step + 1))) + noise * 0.3)

        run.log(
            {
                "loss": loss,
                "accuracy": accuracy,
                "step_time": 0.1 + (step * 0.01) + random.uniform(-0.01, 0.01),
            },
            step=step,
        )

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Step {step:3d}/{args.steps} | loss={loss:.4f} acc={accuracy:.4f}")

        time.sleep(args.delay)

    run.finish(exit_code=0)
    print(f"\n✅ Completed! Total time: {args.steps * args.delay:.1f}s")


if __name__ == "__main__":
    main()
