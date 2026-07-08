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


class RunAlreadyExistsError(Exception):
    """Exception raised when creating a run that already exists without resume.

    Raised by LocalRun (and the tracker API maps it to HTTP 409) when a run
    with the same name already exists in the project and the caller did not
    set resume=True. Appending to the existing file would mix metrics from
    independent run instances and corrupt step numbering, so this is treated
    as an error rather than a warning.
    """

    pass
