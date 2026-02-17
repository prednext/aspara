"""Module-level API for run management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aspara.storage.metrics import resolve_metrics_storage_backend

if TYPE_CHECKING:
    from aspara.run.run import Run


_current_run: Run | None = None
_storage_backend: str = "jsonl"  # Global storage backend setting


def init(
    project: str | None = None,
    name: str | None = None,
    config: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    dir: str | None = None,
    tracker_uri: str | None = None,
    storage_backend: str | None = None,
    project_tags: list[str] | None = None,
) -> Run:
    """Initialize a new run.

    This is the main entry point for starting experiment tracking.
    Similar to wandb.init().

    Args:
        project: Project name. Defaults to "default".
        name: Run name. If None, generates a random name.
        config: Initial configuration parameters.
        tags: List of tags for this run.
        notes: Run notes/description (wandb-compatible).
        dir: Base directory for storing data. Defaults to XDG-based default (~/.local/share/aspara).
        tracker_uri: Tracker server URI for remote mode. If None, uses local file storage.
        storage_backend: Storage backend type ('jsonl' or 'polars'). Can also be set via ASPARA_STORAGE_BACKEND env var.

    Returns:
        The initialized Run object.

    Examples:
        Basic usage with local file storage:

        >>> import aspara
        >>> run = aspara.init(project="my_project", config={"lr": 0.01})
        >>> aspara.log({"loss": 0.5})
        >>> aspara.finish()

        Using remote tracker:

        >>> run = aspara.init(project="my_project", tracker_uri="http://localhost:3142")

        Using Polars backend for efficient storage:

        >>> run = aspara.init(project="my_project", storage_backend="polars")
    """
    global _current_run, _storage_backend

    # Finish previous run if exists
    if _current_run is not None:
        _current_run.finish(quiet=True)

    # Determine storage backend using central resolver
    selected_backend = resolve_metrics_storage_backend(storage_backend)
    _storage_backend = selected_backend

    # Create Run which internally delegates to LocalRun or RemoteRun based on tracker_uri
    from aspara.run.run import Run

    run = Run(
        name=name,
        project=project,
        config=config,
        tags=tags,
        notes=notes,
        dir=dir,
        storage_backend=selected_backend,
        tracker_uri=tracker_uri,
        project_tags=project_tags,
    )
    _current_run = run

    return run


def log(
    data: dict[str, Any],
    step: int | None = None,
    commit: bool = True,
    timestamp: str | None = None,
) -> None:
    """Log metrics to the current run.

    Args:
        data: Dictionary of metric names to values
        step: Optional step number. If None, auto-increments.
        commit: If True, commits the step.
        timestamp: Optional timestamp in ISO format. If None, uses current time.

    Raises:
        RuntimeError: If no run is active

    Examples:
        >>> import aspara
        >>> aspara.init(project="test")
        >>> aspara.log({"loss": 0.5, "accuracy": 0.95})
    """
    if _current_run is None:
        raise RuntimeError("No active run. Call aspara.init() first.")

    _current_run.log(data, step=step, commit=commit, timestamp=timestamp)


def finish(exit_code: int = 0, quiet: bool = False) -> None:
    """Finish the current run.

    Similar to wandb.finish().

    Args:
        exit_code: Exit code for the run (0 = success)
        quiet: If True, suppress output messages

    Examples:
        >>> import aspara
        >>> aspara.init(project="test")
        >>> aspara.log({"loss": 0.5})
        >>> aspara.finish()
    """
    global _current_run

    if _current_run is not None:
        _current_run.finish(exit_code=exit_code, quiet=quiet)
        _current_run = None


def get_current_run() -> Run | None:
    """Get the current active run.

    Returns:
        The current Run object, or None if no run is active.
    """
    return _current_run
