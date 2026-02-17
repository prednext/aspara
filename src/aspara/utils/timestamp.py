"""Timestamp parsing and normalization utilities.

This module provides unified timestamp parsing functions for the aspara library.
All functions raise ValueError for invalid input and do not accept None.
"""

from __future__ import annotations

from datetime import datetime, timezone


def parse_to_datetime(ts_value: str | int | float | datetime) -> datetime:
    """Parse various timestamp formats to UTC datetime.

    Args:
        ts_value: Timestamp in one of:
            - datetime: returned as-is (UTC ensured)
            - int/float: Unix timestamp in milliseconds
            - str: ISO 8601 format string

    Returns:
        datetime object in UTC timezone.

    Raises:
        ValueError: If input is None, empty string, or invalid format.
    """
    if ts_value is None:
        raise ValueError("Timestamp cannot be None")

    if isinstance(ts_value, datetime):
        # Ensure timezone-aware
        if ts_value.tzinfo is None:
            return ts_value.replace(tzinfo=timezone.utc)
        return ts_value

    if isinstance(ts_value, (int, float)):
        return datetime.fromtimestamp(ts_value / 1000, tz=timezone.utc)

    if isinstance(ts_value, str):
        ts_str = ts_value.strip()
        if not ts_str:
            raise ValueError("Timestamp string cannot be empty")

        # Handle ISO 8601 format with 'Z' suffix
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(ts_str)
        except ValueError as exc:
            raise ValueError("Invalid timestamp format. Expected ISO 8601 string or UNIX milliseconds.") from exc

        # Ensure timezone-aware
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    raise ValueError(f"Unsupported timestamp type: {type(ts_value)}. Expected datetime, int, float, or ISO 8601 string.")


def parse_to_ms(ts_value: str | int | float | datetime) -> int:
    """Normalize timestamp to UNIX milliseconds.

    Args:
        ts_value: Timestamp in one of:
            - datetime: converted to UNIX milliseconds
            - int/float: treated as UNIX time in milliseconds
            - str: parsed as ISO 8601 format string

    Returns:
        int: UNIX timestamp in milliseconds.

    Raises:
        ValueError: If input is None, empty string, or invalid format.
    """
    if ts_value is None:
        raise ValueError("Timestamp cannot be None")

    # Numeric -> treat as UNIX ms
    if isinstance(ts_value, (int, float)):
        return int(ts_value)

    # Other types -> parse to datetime first, then convert to ms
    dt = parse_to_datetime(ts_value)
    return int(dt.timestamp() * 1000)
