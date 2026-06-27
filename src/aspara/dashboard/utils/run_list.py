"""Helpers for parsing and validating comma-separated run lists."""

from __future__ import annotations

from aspara.config import get_resource_limits
from aspara.utils import validators


def parse_and_validate_run_list(runs: str) -> list[str]:
    """Parse comma-separated run names and validate them.

    Args:
        runs: Comma-separated run names (e.g. ``"run1,run2,run3"``).

    Returns:
        List of validated, stripped run names.

    Raises:
        ValueError: If no runs are specified, too many runs are requested,
            or any run name fails validation.
    """
    if not runs:
        raise ValueError("No runs specified")

    run_list = [r.strip() for r in runs.split(",") if r.strip()]
    if not run_list:
        raise ValueError("No valid runs specified")

    limits = get_resource_limits()
    if len(run_list) > limits.max_metric_names:
        raise ValueError(f"Too many runs: {len(run_list)} (max: {limits.max_metric_names})")

    for run_name in run_list:
        validators.validate_run_name(run_name)

    return run_list
