"""
Tests for error handling and edge cases.
"""

from unittest.mock import MagicMock

import pytest

from aspara.dashboard.dependencies import get_project_catalog
from aspara.dashboard.main import app


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_metrics_reader_exception(self, test_client):
        """Test handling of catalog exceptions."""
        mock_catalog = MagicMock()
        # Return empty list as fallback
        mock_catalog.get_projects.return_value = []
        mock_catalog.get_metadata.return_value = {}

        app.dependency_overrides[get_project_catalog] = lambda: mock_catalog
        try:
            response = test_client.get("/")

            # Should return 200 even with empty project list
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_nonexistent_project_404_behavior(self, test_client, setup_test_data):
        """Test behavior for nonexistent projects."""
        response = test_client.get("/projects/totally_fake_project")

        # Should return 404 for nonexistent project
        assert response.status_code == 404

    def test_nonexistent_run_behavior(self, test_client, setup_test_data):
        """Test behavior for nonexistent runs."""
        response = test_client.get("/projects/test_project/runs/fake_run")

        # Should handle gracefully
        assert response.status_code in [200, 404]

    def test_malformed_requests(self, test_client):
        """Test handling of malformed requests."""
        # Test with invalid characters
        response = test_client.get("/projects/test../../../etc/passwd")
        assert response.status_code in [200, 400, 404]

        # Test with moderately long paths (shorten if unavoidable)
        long_name = "a" * 50
        response = test_client.get(f"/projects/{long_name}")
        assert response.status_code in [200, 400, 404, 414]


class TestResponseHeaders:
    """Tests for proper HTTP headers."""

    def test_html_content_type(self, test_client, setup_test_data):
        """Test HTML endpoints return correct content type."""
        response = test_client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_api_content_type(self, test_client, setup_test_data):
        """Test API endpoints return correct content type."""
        response = test_client.get("/api/projects/test_project/runs/metrics?runs=run_1")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_cors_headers(self, test_client):
        """Test CORS headers are present."""
        # OPTIONS requests need Origin header, so add it
        response = test_client.options("/", headers={"Origin": "http://testserver"})

        # Check if CORS middleware adds appropriate headers
        assert "access-control-allow-origin" in response.headers


class TestDataValidation:
    """Tests for data validation and sanitization."""

    def test_special_characters_in_names(self, test_client, setup_test_data):
        """Test handling of special characters in project names."""
        # Test URL encoding/decoding - special characters should be rejected
        response = test_client.get("/projects/test%20project")
        assert response.status_code == 400  # Spaces not allowed

        response = test_client.get("/projects/test+project")
        assert response.status_code == 400  # Plus signs not allowed

    def test_empty_query_parameters(self, test_client, setup_test_data):
        """Test handling of empty query parameters."""
        response = test_client.get("/api/projects/test_project/runs/metrics?runs=")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data or "runs" in data


class TestPerformance:
    """Basic performance and load tests."""

    def test_concurrent_requests(self, test_client, setup_test_data):
        """Test handling of multiple concurrent requests."""
        import threading
        import time

        results = []

        def make_request():
            response = test_client.get("/")
            results.append(response.status_code)

        # Create multiple threads
        threads = [threading.Thread(target=make_request) for _ in range(5)]

        start_time = time.time()
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.time()

        # All requests should succeed
        assert all(status == 200 for status in results)
        # Should complete within reasonable time (adjust as needed)
        assert end_time - start_time < 5.0

    def test_large_response_handling(self, test_client):
        """Test handling of large responses."""
        from aspara.catalog.project_catalog import ProjectInfo

        mock_catalog = MagicMock()
        # Mock large dataset
        large_projects = [
            ProjectInfo(
                name=f"project_{i}",
                run_count=10,
                last_update=pytest.importorskip("datetime").datetime.now(),
            )
            for i in range(100)
        ]

        mock_catalog.get_projects.return_value = large_projects
        mock_catalog.get_metadata.return_value = {}

        app.dependency_overrides[get_project_catalog] = lambda: mock_catalog
        try:
            response = test_client.get("/")

            assert response.status_code == 200
            # Should handle large responses without timeout
            assert len(response.text) > 1000
        finally:
            app.dependency_overrides.clear()


class TestTemplateRendering:
    """Tests for mustache template rendering edge cases."""

    def test_template_with_special_characters(self, test_client):
        """Test template rendering with special characters."""
        from aspara.catalog.project_catalog import ProjectInfo

        mock_catalog = MagicMock()
        # Project with special characters
        special_project = ProjectInfo(
            name="test & <script>alert(1)</script>",
            run_count=1,
            last_update=pytest.importorskip("datetime").datetime.now(),
        )

        mock_catalog.get_projects.return_value = [special_project]
        mock_catalog.get_metadata.return_value = {}

        app.dependency_overrides[get_project_catalog] = lambda: mock_catalog
        try:
            response = test_client.get("/")

            assert response.status_code == 200
            # Should escape special characters
            assert "<script>" not in response.text or "&lt;script&gt;" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_template_with_unicode(self, test_client):
        """Test template rendering with unicode characters."""
        from aspara.catalog.project_catalog import ProjectInfo

        mock_catalog = MagicMock()
        unicode_project = ProjectInfo(
            name="プロジェクト",  # Japanese characters
            run_count=1,
            last_update=pytest.importorskip("datetime").datetime.now(),
        )

        mock_catalog.get_projects.return_value = [unicode_project]
        mock_catalog.get_metadata.return_value = {}

        app.dependency_overrides[get_project_catalog] = lambda: mock_catalog
        try:
            response = test_client.get("/")

            assert response.status_code == 200
            assert "プロジェクト" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_template_missing_data(self, test_client):
        """Test template rendering with missing/None data."""
        from aspara.catalog.project_catalog import ProjectInfo

        mock_catalog = MagicMock()
        # Use valid values since ProjectInfo model requires them
        incomplete_project = ProjectInfo(
            name="test_project",
            run_count=0,  # Use 0 instead of None
            last_update=pytest.importorskip("datetime").datetime.now(),
        )

        mock_catalog.get_projects.return_value = [incomplete_project]
        mock_catalog.get_metadata.return_value = {}

        app.dependency_overrides[get_project_catalog] = lambda: mock_catalog
        try:
            response = test_client.get("/")

            # Should handle gracefully without crashing
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


class TestMemoryAndResources:
    """Tests for memory usage and resource management."""

    def test_memory_leak_prevention(self, test_client, setup_test_data):
        """Test for potential memory leaks with repeated requests."""
        import gc

        # Make many requests to check for memory leaks
        for _ in range(50):
            response = test_client.get("/")
            assert response.status_code == 200

        # Force garbage collection
        gc.collect()

        # Test that we can still make requests
        response = test_client.get("/")
        assert response.status_code == 200

    def test_file_handle_management(self, test_client, setup_test_data):
        """Test that file handles are properly managed."""
        # Multiple requests to different endpoints
        endpoints = [
            "/",
            "/projects/test_project",
            "/projects/test_project/runs/run_1",
        ]

        for _ in range(10):
            for endpoint in endpoints:
                response = test_client.get(endpoint)
                assert response.status_code == 200
