"""
Unit tests for the FastAPI server endpoints.
"""

import pytest


class TestHomeEndpoint:
    """Tests for the home page (projects list) endpoint."""

    def test_home_returns_html(self, test_client, setup_test_data):
        """Test that home page returns HTML content."""
        response = test_client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
        assert "Aspara" in response.text

    def test_home_contains_projects(self, test_client, setup_test_data):
        """Test that home page displays project data."""
        response = test_client.get("/")

        assert response.status_code == 200
        assert "test_project" in response.text
        assert "empty_project" in response.text
        assert "Projects" in response.text


class TestProjectRunsEndpoints:
    """Tests for project runs list endpoints."""

    def test_project_runs_list_html(self, test_client, setup_test_data):
        """Test project runs list returns HTML."""
        response = test_client.get("/projects/test_project")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "run_1" in response.text
        assert "run_2" in response.text

    def test_project_runs_list_empty_project(self, test_client, setup_test_data):
        """Test runs list for empty project."""
        response = test_client.get("/projects/empty_project")

        assert response.status_code == 200
        assert "No runs found" in response.text

    def test_project_runs_list_nonexistent_project(self, test_client, setup_test_data):
        """Test runs list for nonexistent project returns 404."""
        response = test_client.get("/projects/nonexistent")

        assert response.status_code == 404


class TestRunsEndpoints:
    """Tests for runs-related endpoints."""


class TestRunDetailEndpoints:
    """Tests for run detail endpoints."""

    def test_run_detail_html(self, test_client, setup_test_data):
        """Test run detail returns HTML."""
        response = test_client.get("/projects/test_project/runs/run_1")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "run_1" in response.text
        assert "Parameters" in response.text
        assert "Code & Artifacts" in response.text


class TestCompareEndpoint:
    """Tests for run comparison endpoint."""

    def test_compare_runs(self, test_client, setup_test_data):
        """Test runs metrics endpoint."""
        response = test_client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2")

        assert response.status_code == 200
        data = response.json()
        assert "project" in data
        assert "metrics" in data  # New format uses "metrics" key
        assert data["project"] == "test_project"


class TestStaticFiles:
    """Tests for static file serving."""

    def test_static_css_accessible(self, test_client):
        """Test that static CSS files are accessible."""
        response = test_client.get("/static/dist/css/styles.css")

        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")

    def test_static_js_accessible(self, test_client):
        """Test that static JS files are accessible."""
        response = test_client.get("/static/js/chart.js")

        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "") or "text/plain" in response.headers.get("content-type", "")


@pytest.mark.parametrize(
    "endpoint",
    [
        "/",
        "/projects/test_project",
        "/projects/test_project/runs/run_1",
    ],
)
def test_html_endpoints_have_required_elements(test_client, setup_test_data, endpoint):
    """Test that HTML endpoints contain required UI elements."""
    response = test_client.get(endpoint)

    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text
    assert "<html" in response.text
    assert "<head>" in response.text
    assert "<body" in response.text
    assert "Aspara" in response.text  # App name
    assert "styles.css" in response.text  # CSS framework (Tailwind CSS compiled)
    assert "Inter" in response.text  # Font
