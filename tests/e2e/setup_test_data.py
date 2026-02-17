"""
E2E test data setup script.
Creates test runs with metrics for Playwright E2E tests.
"""

import random

import aspara


def generate_metrics(step: int, total_steps: int) -> dict[str, float]:
    """Generate sample metrics for a given step."""
    progress = step / total_steps

    # Training metrics (improving over time)
    train_loss = 1.0 * (1 - progress * 0.8) + random.gauss(0, 0.05)
    train_accuracy = 0.3 + progress * 0.6 + random.gauss(0, 0.02)

    # Validation metrics (slightly worse than training)
    val_loss = train_loss * 1.1 + random.gauss(0, 0.03)
    val_accuracy = train_accuracy * 0.95 + random.gauss(0, 0.02)

    return {
        "loss": max(0.01, train_loss),
        "accuracy": max(0.0, min(1.0, train_accuracy)),
        "val_loss": max(0.01, val_loss),
        "val_accuracy": max(0.0, min(1.0, val_accuracy)),
    }


def create_test_run(project: str, run_name: str, steps: int = 50) -> None:
    """Create a test run with metrics."""
    print(f"Creating run: {project}/{run_name} ({steps} steps)")

    aspara.init(
        project=project,
        name=run_name,
        config={
            "learning_rate": 0.01,
            "batch_size": 32,
            "optimizer": "adam",
            "model_type": "mlp",
        },
        tags=["e2e-test"],
    )

    for step in range(steps):
        metrics = generate_metrics(step, steps)
        aspara.log(metrics, step=step)

    aspara.finish()
    print(f"  Completed: {run_name}")


def create_empty_run(project: str, run_name: str) -> None:
    """Create an empty run without metrics."""
    print(f"Creating empty run: {project}/{run_name}")

    aspara.init(
        project=project,
        name=run_name,
        config={"test": "empty"},
        tags=["e2e-test", "empty"],
    )

    # Finish without logging any metrics
    aspara.finish()
    print(f"  Completed: {run_name} (empty)")


def main() -> None:
    """Set up all test data for E2E tests."""
    project = "default"

    print("=" * 50)
    print("Setting up E2E test data")
    print("=" * 50)

    # Create main test run
    create_test_run(project, "test_run", steps=50)

    # Create comparison runs
    create_test_run(project, "run_1", steps=50)
    create_test_run(project, "run_2", steps=50)

    # Create empty run for error handling test
    create_empty_run(project, "empty_run")

    print("=" * 50)
    print("E2E test data setup complete!")
    print(f"Project: {project}")
    print("Runs: test_run, run_1, run_2, empty_run")
    print("=" * 50)


if __name__ == "__main__":
    main()
