"""
Pydantic models for metadata validation.

This module provides Pydantic models for validating metadata updates
with resource limits integration.
"""

from typing import Any

from pydantic import BaseModel, field_validator

from aspara.config import get_resource_limits

__all__ = ["MetadataUpdate", "validate_metadata"]


class MetadataUpdate(BaseModel):
    """Model for validating metadata updates.

    Validates notes and tags against configured resource limits.
    All fields are optional to support partial updates.
    """

    notes: str | None = None
    tags: list[str] | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes_type(cls, v: Any) -> str | None:
        """Validate notes type and length against resource limits."""
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("notes must be a string")
        limits = get_resource_limits()
        if len(v) > limits.max_notes_length:
            raise ValueError(f"notes exceeds maximum length: {len(v)} characters (max: {limits.max_notes_length})")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags_type_and_count(cls, v: Any) -> list[str] | None:
        """Validate tags type and count against resource limits."""
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        limits = get_resource_limits()
        if len(v) > limits.max_tags_count:
            raise ValueError(f"Too many tags: {len(v)} (max: {limits.max_tags_count})")
        # Validate each tag is a string
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("All tags must be strings")
        return v


def validate_metadata(metadata: dict[str, Any]) -> None:
    """Validate metadata dictionary using Pydantic model.

    This function provides a simple interface for validating metadata
    dictionaries, converting Pydantic ValidationError to ValueError
    for backwards compatibility.

    Args:
        metadata: Metadata dictionary to validate. May contain 'notes' and/or 'tags'.

    Raises:
        ValueError: If validation fails.
    """
    from pydantic import ValidationError

    try:
        MetadataUpdate.model_validate(metadata)
    except ValidationError as e:
        # Extract the first error message for backwards compatibility
        error = e.errors()[0]
        raise ValueError(error["msg"]) from None
