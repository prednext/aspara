"""Run package - experiment tracking core.

This package provides the core run tracking functionality for aspara.
Users should use the Run class or module-level API (init, log, finish)
for creating and managing runs.

Example:
    >>> from aspara.run import Run, init, log, finish
    >>> run = init(project="my_project")
    >>> log({"loss": 0.5})
    >>> finish()
"""

from aspara.run._api import finish, get_current_run, init, log
from aspara.run._config import Config
from aspara.run._summary import Summary
from aspara.run.run import Run

# LocalRun/RemoteRun are internal implementation details
# Users should use the Run class

__all__ = [
    "Run",
    "Config",
    "Summary",
    "init",
    "log",
    "finish",
    "get_current_run",
]
