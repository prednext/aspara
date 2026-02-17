"""
Template rendering service for Aspara Dashboard.

Provides Mustache template rendering and context formatting utilities.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pystache

from aspara.catalog import ProjectInfo, RunInfo

BASE_DIR = Path(__file__).parent.parent
_mustache_renderer = pystache.Renderer(search_dirs=[str(BASE_DIR / "templates")])


def create_breadcrumbs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create standardized breadcrumbs with consistent formatting.

    Args:
        items: List of breadcrumb items with 'label' and optional 'url' keys.
              First item is assumed to be Home.

    Returns:
        List of breadcrumb items with consistent is_not_first flags.
    """
    result = []

    for i, item in enumerate(items):
        crumb = item.copy()
        crumb["is_not_first"] = i != 0

        # Add home icon to first item if not already specified
        if i == 0 and "is_home" not in crumb:
            crumb["is_home"] = True

        result.append(crumb)

    return result


def render_mustache_response(template_name: str, context: dict[str, Any]) -> str:
    """Render mustache template with context.

    Args:
        template_name: Name of the template file (without extension).
        context: Template context dictionary.

    Returns:
        Rendered HTML string.
    """
    # Add common context variables
    context.update({
        "current_year": datetime.now().year,
        "page_title": context.get("page_title", "Aspara"),
    })

    # Render content template
    content = _mustache_renderer.render_name(template_name, context)

    # Render layout with content
    layout_context = context.copy()
    layout_context["content"] = content

    return _mustache_renderer.render_name("layout", layout_context)


class TemplateService:
    """Service for template rendering and data formatting.

    This class provides methods for formatting data objects for template rendering.
    """

    @staticmethod
    def format_project_for_template(project: ProjectInfo, tags: list[str] | None = None) -> dict[str, Any]:
        """Format a ProjectInfo for template rendering.

        Args:
            project: ProjectInfo object.
            tags: Optional list of tags from metadata.

        Returns:
            Dictionary suitable for template rendering.
        """
        return {
            "name": project.name,
            "run_count": project.run_count or 0,
            "last_update": int(project.last_update.timestamp() * 1000) if project.last_update else 0,
            "formatted_last_update": (project.last_update.strftime("%B %d, %Y at %I:%M %p") if project.last_update else "N/A"),
            "tags": tags or [],
        }

    @staticmethod
    def format_run_for_list(run: RunInfo) -> dict[str, Any]:
        """Format a RunInfo for runs list template.

        Args:
            run: RunInfo object.

        Returns:
            Dictionary suitable for runs list template rendering.
        """
        return {
            "name": run.name,
            "param_count": run.param_count or 0,
            "last_update": int(run.last_update.timestamp() * 1000) if run.last_update else 0,
            "formatted_last_update": (run.last_update.strftime("%B %d, %Y at %I:%M %p") if run.last_update else "N/A"),
            "is_corrupted": run.is_corrupted,
            "error_message": run.error_message,
            "tags": run.tags,
            "has_tags": len(run.tags) > 0,
            "is_finished": run.is_finished,
            "is_wip": run.status.value == "wip",
            "status": run.status.value,
        }

    @staticmethod
    def format_run_for_project_detail(run: RunInfo) -> dict[str, Any] | None:
        """Format a RunInfo for project detail template (excludes corrupted runs).

        Args:
            run: RunInfo object.

        Returns:
            Dictionary suitable for project detail template rendering,
            or None if the run is corrupted.
        """
        if run.is_corrupted:
            return None

        return {
            "name": run.name,
            "last_update": int(run.last_update.timestamp() * 1000) if run.last_update else 0,
            "formatted_last_update": (run.last_update.strftime("%B %d, %Y at %I:%M %p") if run.last_update else "N/A"),
            "is_finished": run.is_finished,
            "is_wip": run.status.value == "wip",
            "status": run.status.value,
        }

    @staticmethod
    def format_artifact_for_template(artifact: dict[str, Any]) -> dict[str, Any]:
        """Format an artifact for template rendering with category flags.

        Args:
            artifact: Artifact dictionary.

        Returns:
            Dictionary with category boolean flags added.
        """
        category = artifact.get("category")
        return {
            **artifact,
            "is_code": category == "code",
            "is_config": category == "config",
            "is_model": category == "model",
            "is_data": category == "data",
            "is_other": category == "other" or category is None,
        }
