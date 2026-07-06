"""
Tests for ProjectCatalog
"""

import json
from datetime import timezone

import pytest

from aspara.catalog import ProjectCatalog


@pytest.fixture
def temp_catalog_dir(tmp_path):
    """Fixture to provide a temporary directory"""
    return tmp_path


def test_project_catalog_list(temp_catalog_dir):
    """Test that ProjectCatalog's list method works correctly"""

    catalog = ProjectCatalog(str(temp_catalog_dir))

    # Create test directories
    (temp_catalog_dir / "project1").mkdir()
    (temp_catalog_dir / "project2").mkdir()
    (temp_catalog_dir / "not_a_project.txt").write_text("This is not a project directory")

    # Get project list
    projects = catalog.get_projects()

    # Verify results
    assert len(projects) == 2
    project_names = [p.name for p in projects]
    assert "project1" in project_names
    assert "project2" in project_names
    assert "not_a_project.txt" not in project_names


def test_project_catalog_ignores_hidden_dirs(temp_catalog_dir):
    """Hidden/reserved directories (e.g. .queue) must not be listed as projects.

    Such names fail validate_name() and would crash the dashboard home page if
    returned by get_projects().
    """
    catalog = ProjectCatalog(str(temp_catalog_dir))

    (temp_catalog_dir / "project1").mkdir()
    (temp_catalog_dir / ".queue").mkdir()
    (temp_catalog_dir / ".hidden").mkdir()

    projects = catalog.get_projects()
    project_names = [p.name for p in projects]
    assert project_names == ["project1"]


def test_project_last_update_is_timezone_aware(temp_catalog_dir):
    """last_update must be timezone-aware UTC, not naive local time.

    Naive datetimes from datetime.fromtimestamp() would raise TypeError when
    compared with aware datetimes elsewhere in the codebase (e.g. in
    _infer_stale_status which uses datetime.now(timezone.utc)).
    """
    catalog = ProjectCatalog(str(temp_catalog_dir))
    (temp_catalog_dir / "project1").mkdir()
    (temp_catalog_dir / "project1" / "run1.jsonl").write_text("{}\n")

    projects = catalog.get_projects()
    assert len(projects) == 1
    assert projects[0].last_update.tzinfo is not None
    assert projects[0].last_update.tzinfo == timezone.utc


def test_project_get_last_update_is_timezone_aware(temp_catalog_dir):
    """get() must also return timezone-aware UTC last_update."""
    catalog = ProjectCatalog(str(temp_catalog_dir))
    (temp_catalog_dir / "project1").mkdir()
    (temp_catalog_dir / "project1" / "run1.jsonl").write_text("{}\n")

    project = catalog.get("project1")
    assert project.last_update.tzinfo is not None
    assert project.last_update.tzinfo == timezone.utc


def test_project_catalog_get_projects_with_metadata(temp_catalog_dir):
    """get_projects_with_metadata() returns project info and metadata in one pass."""
    catalog = ProjectCatalog(str(temp_catalog_dir))

    (temp_catalog_dir / "project1").mkdir()
    (temp_catalog_dir / "project1" / "run1.jsonl").write_text("{}\n")
    (temp_catalog_dir / "project1" / "metadata.json").write_text(json.dumps({"notes": "project one", "tags": ["a", "b"]}))

    (temp_catalog_dir / "project2").mkdir()
    (temp_catalog_dir / "project2" / "run1.jsonl").write_text("{}\n")
    # project2 has no metadata.json -> default metadata

    projects_with_metadata = catalog.get_projects_with_metadata()

    assert len(projects_with_metadata) == 2
    names = [project.name for project, _ in projects_with_metadata]
    assert names == ["project1", "project2"]

    metadata1 = projects_with_metadata[0][1]
    assert metadata1["notes"] == "project one"
    assert metadata1["tags"] == ["a", "b"]

    metadata2 = projects_with_metadata[1][1]
    assert metadata2["notes"] == ""
    assert metadata2["tags"] == []


def test_project_catalog_get_projects_with_metadata_ignores_hidden_dirs(temp_catalog_dir):
    """get_projects_with_metadata() must skip hidden directories like get_projects()."""
    catalog = ProjectCatalog(str(temp_catalog_dir))

    (temp_catalog_dir / "project1").mkdir()
    (temp_catalog_dir / ".queue").mkdir()

    projects_with_metadata = catalog.get_projects_with_metadata()

    assert len(projects_with_metadata) == 1
    assert projects_with_metadata[0][0].name == "project1"
