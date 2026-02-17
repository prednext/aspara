"""Metadata utilities for project-level operations."""

from __future__ import annotations

from pathlib import Path


def update_project_metadata_tags(base_dir: str | Path, project_name: str, new_tags: list[str] | None) -> None:
    """Append tags to project-level metadata file.

    This writes to {base_dir}/{project_name}/metadata.json in the standard
    project metadata format (notes, tags, created_at, updated_at) used by
    the dashboard/catalog layer.
    """
    if not new_tags:
        return

    # Use ProjectCatalog metadata API so that project-level metadata.json
    # is managed through the shared catalog/metadata_utils helpers.
    from aspara.catalog import ProjectCatalog

    base_dir_path = Path(base_dir)
    catalog = ProjectCatalog(base_dir_path)

    existing_metadata = catalog.get_metadata(project_name)

    # Merge tags and remove duplicates while preserving order
    existing_tags = [t for t in (existing_metadata.get("tags") or []) if isinstance(t, str)]
    added_tags = [t for t in new_tags if isinstance(t, str)]
    seen: set[str] = set()
    merged: list[str] = []
    for tag in existing_tags + added_tags:
        if tag not in seen:
            seen.add(tag)
            merged.append(tag)

    # Only update tags; notes and timestamps are handled by metadata_utils
    try:
        catalog.update_metadata(project_name, {"tags": merged})
    except Exception as e:
        # Log metadata write failures but don't impact run tracking
        from aspara.logger import logger

        logger.warning(f"Failed to update project metadata tags for '{project_name}': {e}")
