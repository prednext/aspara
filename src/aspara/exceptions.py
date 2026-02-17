"""
Aspara exceptions module.

Contains exception classes used across multiple modules to avoid circular dependencies.
"""


class ProjectNotFoundError(Exception):
    """Exception raised when a project is not found."""

    pass


class RunNotFoundError(Exception):
    """Exception raised when a run is not found."""

    pass
