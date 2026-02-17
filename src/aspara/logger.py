"""Logging configuration for Aspara."""

import logging
import sys

# Create logger for Aspara
logger = logging.getLogger("aspara")


def setup_logger(level: int = logging.INFO) -> None:
    """Setup the Aspara logger with default configuration.

    Args:
        level: Logging level (default: INFO)
    """
    if logger.handlers:
        # Already configured
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter("aspara: %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


# Initialize logger on import
setup_logger()
