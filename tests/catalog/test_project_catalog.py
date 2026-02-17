"""
Tests for ProjectCatalog
"""

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
