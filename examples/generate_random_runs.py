"""
Sample script to generate multiple random experiment runs.
Creates 4 different runs, each recording 100 steps of metrics.
"""

import math
import random

import aspara


def generate_metrics_with_trend(
    step: int,
    total_steps: int,
    base_values: dict[str, float],
    noise_levels: dict[str, float],
    trends: dict[str, float],
) -> dict[str, float]:
    """
    Generate metrics with trend and noise.

    Args:
        step: Current step
        total_steps: Total number of steps
        base_values: Initial values for each metric
        noise_levels: Noise level for each metric
        trends: Final change amount for each metric

    Returns:
        Generated metrics
    """
    progress = step / total_steps
    metrics = {}

    for metric_name, base_value in base_values.items():
        # Change due to trend (linear + slight exponential component)
        trend_factor = progress * (1.0 + 0.2 * math.log(1 + 5 * progress))
        trend_change = trends[metric_name] * trend_factor

        # Random noise (sine wave + Gaussian noise)
        noise = (
            noise_levels[metric_name] * math.sin(step * 0.2) * 0.3  # Periodic noise
            + noise_levels[metric_name] * random.gauss(0, 0.5)  # Random noise
        )

        # Calculate final value
        value = base_value + trend_change + noise

        # Limit value range (accuracy between 0-1, loss >= 0)
        if "accuracy" in metric_name:
            value = max(0.0, min(1.0, value))
        elif "loss" in metric_name:
            value = max(0.01, value)

        metrics[metric_name] = value

    return metrics


def create_run_config(run_id: int) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """
    Create configuration for each run.

    Args:
        run_id: Run number

    Returns:
        Tuple of (initial values, noise levels, trends)
    """
    # Set slightly different initial values for each run
    base_values = {
        "accuracy": 0.3 + random.uniform(-0.1, 0.1),
        "loss": 1.0 + random.uniform(-0.2, 0.2),
        "val_accuracy": 0.25 + random.uniform(-0.1, 0.1),
        "val_loss": 1.1 + random.uniform(-0.2, 0.2),
    }

    # Set noise levels
    noise_levels = {
        "accuracy": 0.02 + 0.01 * run_id,
        "loss": 0.05 + 0.02 * run_id,
        "val_accuracy": 0.03 + 0.01 * run_id,
        "val_loss": 0.07 + 0.02 * run_id,
    }

    # Set trends (accuracy increases, loss decreases)
    trends = {
        "accuracy": 0.5 + random.uniform(-0.1, 0.1),  # Upward trend
        "loss": -0.8 + random.uniform(-0.1, 0.1),  # Downward trend
        "val_accuracy": 0.45 + random.uniform(-0.1, 0.1),  # Upward trend (slightly lower than train)
        "val_loss": -0.75 + random.uniform(-0.1, 0.1),  # Downward trend (slightly higher than train)
    }

    return base_values, noise_levels, trends


def generate_run(
    project: str,
    run_id: int,
    total_steps: int = 100,
    project_tags: list[str] | None = None,
    run_name: str | None = None,
) -> None:
    """
    Generate an experiment run with the specified ID.

    Args:
        project: Project name
        run_id: Run number
        total_steps: Number of steps to generate
        project_tags: Common tags for the project
        run_name: Run name (generated from run_id if not specified)
    """
    # Initialize run
    if run_name is None:
        run_name = f"random_training_run_{run_id}"

    print(f"Starting generation of run {run_id} for project '{project}'! ({run_name})")

    # Create run configuration
    base_values, noise_levels, trends = create_run_config(run_id)

    # Add run-specific tags (fruits) to project-common tags (animals)
    fruits = ["apple", "pear", "orange", "grape", "banana", "mango"]
    num_fruit_tags = random.randint(1, len(fruits))
    run_tags = random.sample(fruits, k=num_fruit_tags)

    aspara.init(
        project=project,
        name=run_name,
        config={
            "learning_rate": 0.01 * (1 + 0.2 * run_id),
            "batch_size": 32 * (1 + run_id % 2),
            "optimizer": ["adam", "sgd", "rmsprop", "adagrad"][run_id % 4],
            "model_type": "mlp",
            "hidden_layers": [128, 64, 32],
            "dropout": 0.2 + 0.05 * run_id,
            "epochs": 10,
            "run_id": run_id,
        },
        tags=run_tags,
        project_tags=project_tags,
    )

    # Simulate training loop
    print(f"Generating metrics for {total_steps} steps...")
    for step in range(total_steps):
        # Generate metrics
        metrics = generate_metrics_with_trend(step, total_steps, base_values, noise_levels, trends)

        # Log metrics
        aspara.log(metrics, step=step)

        # Show progress (every 10 steps)
        if step % 10 == 0 or step == total_steps - 1:
            print(f"  Step {step}/{total_steps - 1}: accuracy={metrics['accuracy']:.3f}, loss={metrics['loss']:.3f}")

    # Finish run
    aspara.finish()

    print(f"Completed generation of run {run_id} for project '{project}'!")


def main() -> None:
    """Main function: Generate multiple runs."""
    steps_per_run = 100

    # Cool secret project names
    project_names = [
        "Project_Phoenix",
        "Operation_Midnight",
        "Genesis_Initiative",
        "Project_Prometheus",
    ]

    # Famous SF titles (mix of Western and Japanese works)
    sf_titles = [
        "AKIRA",
        "Ghost_in_the_Shell",
        "Planetes",
        "Steins_Gate",
        "Paprika",
        "Blade_Runner",
        "Dune",
        "Neuromancer",
        "Foundation",
        "The_Martian",
        "Interstellar",
        "Solaris",
        "Hyperion",
        "Snow_Crash",
        "Contact",
        "Arrival",
        "Gravity",
        "Moon",
        "Ex_Machina",
        "Tenet",
    ]

    print(f"Generating {len(project_names)} projects!")
    print(f"   Each project has 4-5 runs! ({steps_per_run} steps per run)")
    animals = ["dog", "cat", "rabbit", "coala", "bear", "goat"]

    # Shuffle SF titles before using
    shuffled_sf_titles = sf_titles.copy()
    random.shuffle(shuffled_sf_titles)
    sf_title_index = 0

    # Generate multiple projects, create 4-5 runs for each project
    for project_name in project_names:
        # Project-common tags (animals)
        num_project_tags = random.randint(1, len(animals))
        project_tags = random.sample(animals, k=num_project_tags)

        num_runs = random.randint(4, 5)
        for run_id in range(num_runs):
            # Use SF title as run name
            run_name = shuffled_sf_titles[sf_title_index % len(shuffled_sf_titles)]
            sf_title_index += 1
            generate_run(project_name, run_id, steps_per_run, project_tags, run_name)
            print("")  # Insert blank line

    print("All runs have been generated!")
    print("   Check them out on the dashboard!")


if __name__ == "__main__":
    main()
