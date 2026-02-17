"""
Run status enumeration and utilities.

This module provides the status enumeration for runs and utilities
for status management and detection.
"""

from enum import Enum


class RunStatus(Enum):
    """Run status enumeration.

    Represents the current state of a run:
    - wip: Work in progress (actively running)
    - failed: Run finished with non-zero exit code
    - maybe_failed: Run likely failed (connection lost, process killed)
    - completed: Run finished successfully (exit code 0)
    """

    WIP = "wip"
    FAILED = "failed"
    MAYBE_FAILED = "maybe_failed"
    COMPLETED = "completed"

    @classmethod
    def from_is_finished_and_exit_code(cls, is_finished: bool, exit_code: int | None) -> "RunStatus":
        """Create status from is_finished flag and exit code.

        Args:
            is_finished: Whether the run has finished
            exit_code: Exit code (0 = success, non-zero = error)

        Returns:
            RunStatus: Appropriate status
        """
        if not is_finished:
            return cls.WIP
        elif exit_code is None:
            return cls.MAYBE_FAILED
        elif exit_code == 0:
            return cls.COMPLETED
        else:
            return cls.FAILED

    def to_is_finished_and_exit_code(self) -> tuple[bool, int | None]:
        """Convert status back to is_finished and exit_code.

        Returns:
            Tuple of (is_finished, exit_code)
        """
        if self == self.WIP:
            return (False, None)
        elif self == self.COMPLETED:
            return (True, 0)
        elif self == self.FAILED:
            return (True, 1)  # Non-zero exit code
        else:  # MAYBE_FAILED
            return (True, None)
