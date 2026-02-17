"""
Aspara - Simple metrics tracking system for machine learning experiments.

This module provides a wandb-compatible API for experiment tracking.

Examples:
    >>> import aspara
    >>> run = aspara.init(project="my_project", config={"lr": 0.01})
    >>> aspara.log({"loss": 0.5, "accuracy": 0.95})
    >>> aspara.finish()
"""

from aspara.run import Config, Run, Summary, finish, init, log
from aspara.run import get_current_run as _get_current_run

__version__ = "0.1.0"
__all__ = [
    "Run",
    "Config",
    "Summary",
    "init",
    "log",
    "finish",
]


# Convenience function for accessing current run's config
def config() -> Config | None:
    """Get the config of the current run."""
    run = _get_current_run()
    return run.config if run else None
