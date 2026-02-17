"""Base class providing shared run state and step management."""

from __future__ import annotations

import uuid
from typing import Any, Literal


class BaseRun:
    """Base class providing shared run state and step management.

    This class is intentionally minimal and focuses on common runtime
    behaviour such as step tracking and finished-state management.
    Concrete run implementations (e.g., LocalRun, RemoteRun) are
    responsible for I/O specifics.
    """

    def __init__(
        self,
        name: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> None:
        # Common attributes (id is set by subclasses)
        self.id: str
        self.name = name or self._generate_run_name()
        self.project = project or "default"
        self.tags = tags or []
        self.notes = notes or ""

        # Step management
        self._current_step: int = 0
        self._step_committed: bool = True
        # Completion flag shared by all runs
        self._finished: bool = False

    # ---- Run ID/Name generation helpers --------------------------------

    @staticmethod
    def _generate_run_id() -> str:
        """Generate a unique run ID.

        Returns:
            16-character unique identifier
        """
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _generate_run_name() -> str:
        """Generate a random run name.

        Returns:
            Human-readable random name (adjective-noun-number format)
        """
        import random

        adjectives = [
            "happy",
            "clever",
            "swift",
            "brave",
            "calm",
            "eager",
            "gentle",
            "kind",
            "lively",
            "proud",
            "quiet",
            "wise",
            "bold",
            "bright",
        ]
        nouns = [
            "falcon",
            "tiger",
            "eagle",
            "wolf",
            "bear",
            "hawk",
            "lion",
            "dolphin",
            "phoenix",
            "dragon",
            "panda",
            "fox",
            "owl",
            "raven",
        ]

        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        num = random.randint(1, 999)

        return f"{adj}-{noun}-{num}"

    # ---- Step / finished state helpers ---------------------------------

    def _ensure_not_finished(self) -> None:
        """Raise if the run has already been finished.

        Both LocalRun and RemoteRun currently use the same error message,
        so we centralize it here.
        """

        if self._finished:
            raise RuntimeError("Cannot log to a finished run")

    def _prepare_step(self, step: int | None, commit: bool) -> int:
        """Prepare the step value before logging.

        This mirrors the existing behaviour:
        - If an explicit step is provided, use it as-is.
        - Otherwise, keep the current step value. Auto-increment happens
          *after* logging when commit=True.
        """

        if step is not None:
            self._current_step = step
        # When step is None and previous step was committed, we keep the
        # current value here and only increment after logging.
        return self._current_step

    def _after_log(self, commit: bool) -> None:
        """Update internal step state after a log call."""

        if commit:
            self._current_step += 1
            self._step_committed = True
        else:
            self._step_committed = False

    def _mark_finished(self) -> bool:
        """Mark the run as finished.

        Returns:
            bool: False if the run was already finished, True otherwise.
        """

        if self._finished:
            return False
        self._finished = True
        return True

    # ---- Public interface (to be implemented by subclasses) ---------------

    def finish(self, exit_code: int = 0, quiet: bool = False) -> None:
        """Finish the run. Implemented by subclasses."""
        raise NotImplementedError

    # ---- Context manager protocol ----------------------------------------

    def __enter__(self) -> BaseRun:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """Exit context manager, ensuring run is finished.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise.
            exc_val: Exception value if an exception was raised, None otherwise.
            exc_tb: Traceback if an exception was raised, None otherwise.

        Returns:
            False to propagate any exceptions that occurred.
        """
        # Set exit_code=1 if exception occurred
        exit_code = 1 if exc_type is not None else 0
        self.finish(exit_code=exit_code, quiet=True)
        return False  # Do not suppress exceptions

    # ---- Metrics validation ----------------------------------------------

    def _validate_metrics(self, data: dict[str, Any]) -> dict[str, float | int]:
        """Validate and normalize metric data.

        This helper enforces a consistent contract for metrics across
        LocalRun and RemoteRun:

        - Metric names must be non-empty strings
        - Values must be int or float

        Args:
            data: Raw metrics mapping provided by the user

        Returns:
            A new dictionary containing only valid metrics.

        Raises:
            ValueError: If a metric name is empty or a value has an
                unsupported type.
        """

        metrics: dict[str, float | int] = {}
        for key, value in data.items():
            if not key:
                raise ValueError("Metric name cannot be empty")
            if isinstance(value, (int, float)):
                metrics[key] = value
            else:
                raise ValueError(f"Unsupported value type for '{key}': {type(value)}. Currently only int and float are supported.")

        return metrics

    # ---- Artifact validation -----------------------------------------

    def _validate_artifact_input(
        self,
        file_path: str,
        name: str | None = None,
        category: str | None = None,
    ) -> tuple[str, str]:
        """Validate artifact input parameters.

        This helper enforces a consistent contract for artifact logging
        across LocalRun and RemoteRun:

        - File path must be non-empty and point to an existing file
        - Category must be one of the allowed values if provided
        - Returns absolute file path and artifact name

        Args:
            file_path: Path to the artifact file
            name: Optional custom name for the artifact
            category: Optional category for the artifact

        Returns:
            A tuple of (absolute_file_path, artifact_name)

        Raises:
            ValueError: If file_path is invalid, file doesn't exist,
                or category is invalid.
        """
        import os

        # Validate file path
        if not file_path:
            raise ValueError("File path cannot be empty")

        abs_file_path = os.path.abspath(file_path)
        if not os.path.exists(abs_file_path):
            raise ValueError(f"File does not exist: {file_path}")

        if not os.path.isfile(abs_file_path):
            raise ValueError(f"Path is not a file: {file_path}")

        # Determine artifact name
        artifact_name = name or os.path.basename(abs_file_path)
        if not artifact_name:
            raise ValueError("Artifact name cannot be empty")

        # Validate category if provided
        if category is not None and category not in ("code", "model", "config", "data", "other"):
            raise ValueError(f"Invalid category: {category}. Must be one of: code, model, config, data, other")

        return abs_file_path, artifact_name
