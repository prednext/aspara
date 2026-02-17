"""Run class with composition pattern for backend delegation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aspara.run._config import Config
    from aspara.run._local_run import LocalRun
    from aspara.run._remote_run import RemoteRun
    from aspara.run._summary import Summary


class Run:
    """Run class that delegates to either LocalRun or RemoteRun.

    This class provides a unified interface for creating runs. When tracker_uri is provided,
    it creates and delegates to a RemoteRun instance. Otherwise, it creates and delegates
    to a LocalRun instance.
    """

    __slots__ = ("_backend",)
    _backend: LocalRun | RemoteRun

    def __init__(
        self,
        name: str | None = None,
        project: str | None = None,
        config: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        dir: str | None = None,
        storage_backend: str | None = None,
        tracker_uri: str | None = None,
        project_tags: list[str] | None = None,
    ) -> None:
        """Create a new run instance.

        Args:
            name: Name of the run. If None, generates a random name.
            project: Project name this run belongs to. Defaults to "default".
            config: Initial configuration parameters.
            tags: List of tags for this run.
            notes: Run notes/description (wandb-compatible).
            dir: Base directory for storing data. If None, uses XDG-based default (~/.local/share/aspara).
            storage_backend: Storage backend type ('jsonl' or 'polars'). Defaults to 'jsonl'.
            tracker_uri: Tracker server URI for remote mode. If None, uses local file storage.
            project_tags: List of tags to add to the project.
        """
        if tracker_uri is not None:
            from aspara.run._remote_run import RemoteRun

            self._backend = RemoteRun(
                name=name,
                project=project,
                config=config,
                tags=tags,
                notes=notes,
                tracker_uri=tracker_uri,
                project_tags=project_tags,
            )
        else:
            from aspara.run._local_run import LocalRun

            self._backend = LocalRun(
                name=name,
                project=project,
                config=config,
                tags=tags,
                notes=notes,
                dir=dir,
                storage_backend=storage_backend,
                project_tags=project_tags,
            )

    # ---- Property delegations ----------------------------------------

    @property
    def id(self) -> str:
        """Unique run identifier."""
        return self._backend.id

    @property
    def name(self) -> str:
        """Run name."""
        return self._backend.name

    @property
    def project(self) -> str:
        """Project name this run belongs to."""
        return self._backend.project

    @property
    def tags(self) -> list[str]:
        """List of tags for this run."""
        return self._backend.tags

    @property
    def notes(self) -> str:
        """Run notes/description."""
        return self._backend.notes

    @property
    def config(self) -> Config:
        """Configuration parameters."""
        return self._backend.config

    @property
    def summary(self) -> Summary:
        """Run summary data."""
        return self._backend.summary

    @property
    def _finished(self) -> bool:
        """Whether the run has finished."""
        return self._backend._finished

    @property
    def _current_step(self) -> int:
        """Current step number."""
        return self._backend._current_step

    # ---- Method delegations ----------------------------------------

    def log(
        self,
        data: dict[str, Any],
        step: int | None = None,
        commit: bool = True,
        timestamp: str | None = None,
    ) -> None:
        """Log metrics and other data.

        Args:
            data: Dictionary of metric names to values
            step: Optional step number. If None, auto-increments.
            commit: If True, commits the step. If False, accumulates data.
            timestamp: Optional timestamp in ISO format. If None, uses current time.
        """
        self._backend.log(data, step=step, commit=commit, timestamp=timestamp)

    def finish(self, exit_code: int = 0, quiet: bool = False) -> None:
        """Finish the run.

        Args:
            exit_code: Exit code for the run (0 = success)
            quiet: If True, suppress output messages
        """
        self._backend.finish(exit_code=exit_code, quiet=quiet)

    def flush(self, *args: Any, **kwargs: Any) -> Any:
        """Ensure all data is persisted.

        For LocalRun this is a no-op. For RemoteRun this flushes queued metrics.
        """
        return self._backend.flush(*args, **kwargs)

    def log_artifact(
        self,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
    ) -> None:
        """Log an artifact file for this run.

        Args:
            file_path: Path to the file to be logged as an artifact
            name: Optional custom name for the artifact. If None, uses the filename.
            description: Optional description of the artifact
            category: Optional category ('code', 'model', 'config', 'data', 'other')
        """
        self._backend.log_artifact(file_path, name=name, description=description, category=category)

    def set_tags(self, tags: list[str]) -> None:
        """Set tags for this run.

        Args:
            tags: List of tags

        Note:
            This method is only available for local runs.
        """
        self._backend.set_tags(tags)

    # ---- Context manager protocol ----------------------------------------

    def __enter__(self) -> Run:
        """Enter context manager."""
        self._backend.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit context manager, ensuring run is finished."""
        return self._backend.__exit__(exc_type, exc_val, exc_tb)

    # ---- Testing utilities ----------------------------------------

    @property
    def backend(self) -> LocalRun | RemoteRun:
        """Access to the underlying backend implementation.

        This property is intended for testing purposes to verify
        which backend type was created.
        """
        return self._backend
