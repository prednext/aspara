"""Tests for project tags display on the projects list page.

These tests verify that project-level metadata tags written to
<data_dir>/<project>/metadata.json are exposed to the projects_list
Mustache template and end up in the rendered HTML (both visually
and in data-tags for search).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from aspara.dashboard.main import app


def _write_project_metadata(base_dir: Path, project: str, tags: list[str]) -> None:
    project_dir = base_dir / project
    project_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = project_dir / "metadata.json"
    metadata = {
        "notes": "",
        "tags": tags,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def test_projects_list_includes_project_tags_in_html():
    """Home page should render project tags from metadata.json next to project name."""
    from aspara.catalog.project_catalog import ProjectCatalog, ProjectInfo
    from aspara.dashboard.dependencies import configure_data_dir

    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir)

        # Prepare a fake project with metadata tags
        project_name = "test_project"
        _write_project_metadata(data_dir, project_name, ["dog", "cat"])

        # ProjectCatalog.get_projects() will be overridden to return a single project
        mock_projects = [
            ProjectInfo(
                name=project_name,
                run_count=3,
                last_update=Path(temp_dir).stat().st_mtime_ns and Path(temp_dir).stat().st_mtime,
            )
        ]

        # Use a real ProjectCatalog so that get_metadata() is exercised; only get_projects() is overridden.
        catalog = ProjectCatalog(data_dir)
        catalog.get_projects = lambda: mock_projects

        # Configure the data directory
        configure_data_dir(str(data_dir))

        try:
            with patch("aspara.dashboard.dependencies.get_project_catalog", return_value=catalog):
                client = TestClient(app)
                response = client.get("/")

                assert response.status_code == 200
                html = response.text

                # Project name should be present
                assert project_name in html

                # data-tags attribute should contain the project tags (trailing space allowed)
                assert 'data-tags="dog cat' in html

                # Visible tag chips should also contain the labels
                assert ">dog<" in html
                assert ">cat<" in html
        finally:
            # Reset configuration
            configure_data_dir(None)


def test_projects_list_search_uses_project_tags():
    """Projects search should be able to use tags via data-tags attribute.

    This test only verifies that tags appear in data-tags for now, which is
    what the JS search implementation reads. JS behaviour itself is covered
    by frontend tests.
    """
    from aspara.catalog.project_catalog import ProjectCatalog, ProjectInfo
    from aspara.dashboard.dependencies import configure_data_dir

    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir)

        project_name = "tagged_project"
        _write_project_metadata(data_dir, project_name, ["bear", "goat"])

        # ProjectCatalog.get_projects() will be overridden to return a single project
        mock_projects = [
            ProjectInfo(
                name=project_name,
                run_count=1,
                last_update=Path(temp_dir).stat().st_mtime_ns and Path(temp_dir).stat().st_mtime,
            )
        ]

        # Use a real ProjectCatalog so that get_metadata() is exercised; only get_projects() is overridden.
        catalog = ProjectCatalog(data_dir)
        catalog.get_projects = lambda: mock_projects

        # Configure the data directory
        configure_data_dir(str(data_dir))

        try:
            with patch("aspara.dashboard.dependencies.get_project_catalog", return_value=catalog):
                client = TestClient(app)
                response = client.get("/")

                assert response.status_code == 200
                html = response.text

                # Ensure tags are exposed in data-tags; JS uses this for filtering.
                assert 'data-tags="bear goat' in html
        finally:
            # Reset configuration
            configure_data_dir(None)
