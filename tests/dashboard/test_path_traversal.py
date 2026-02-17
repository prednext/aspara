"""
Security tests for path traversal vulnerability protection.

Tests to verify that the Dashboard properly validates and rejects
path traversal attempts in project/run names.
"""

from fastapi.testclient import TestClient

from aspara.dashboard.main import app


class TestPathTraversalProtection:
    """Tests for path traversal vulnerability protection."""

    def test_path_traversal_in_project_name(self):
        """Test that path traversal attempts in project names are rejected."""
        client = TestClient(app)

        # Test various path traversal patterns
        malicious_projects = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc",
            "....//....//....//etc",
            "test/../../../etc",
        ]

        for project in malicious_projects:
            # Test on project detail endpoint
            response = client.get(f"/projects/{project}")
            assert response.status_code in [400, 404], f"Path traversal not blocked for project: {project}"

            # Test on API endpoint
            response = client.get(f"/api/projects/{project}/runs")
            assert response.status_code in [400, 404], f"Path traversal not blocked on API for project: {project}"

    def test_path_traversal_in_run_name(self):
        """Test that path traversal attempts in run names are rejected."""
        client = TestClient(app)

        # Test various path traversal patterns
        malicious_runs = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc",
            "....//....//....//etc",
            "test/../../../etc",
        ]

        for run in malicious_runs:
            # Test on run detail endpoint (with valid project name)
            response = client.get(f"/projects/test_project/runs/{run}")
            assert response.status_code in [400, 404], f"Path traversal not blocked for run: {run}"

            # Test on API endpoint
            response = client.get(f"/api/projects/test_project/runs/{run}/metrics")
            assert response.status_code in [400, 404], f"Path traversal not blocked on API for run: {run}"

    def test_special_characters_rejected(self):
        """Test that special characters in names are properly rejected."""
        client = TestClient(app)

        # Characters that should be rejected
        # Note: Slashes cause routing issues and may return 404 instead of 400
        invalid_chars_projects = [
            "project with spaces",
            "project..name",
            "project$name",
            "project%name",
            "project&name",
            "project*name",
        ]

        for project in invalid_chars_projects:
            response = client.get(f"/projects/{project}")
            # Should return 400 for validation error (not 404)
            assert response.status_code == 400, f"Special characters not rejected for: {project}"
            if response.status_code == 400:
                data = response.json()
                assert "Invalid project name" in data["detail"]

        # Slashes may be handled by routing layer and return 404
        slash_projects = [
            "project/with/slashes",
            "project\\with\\backslashes",
        ]
        for project in slash_projects:
            response = client.get(f"/projects/{project}")
            # Either validation error or routing error is acceptable
            assert response.status_code in [400, 404], f"Slashes not blocked for: {project}"

    def test_valid_names_accepted(self):
        """Test that valid project/run names are accepted."""
        client = TestClient(app)

        # Valid characters: alphanumeric, underscore, hyphen
        valid_names = [
            "test_project",
            "test-project",
            "TestProject123",
            "project_123-test",
            "a1b2c3",
        ]

        for name in valid_names:
            # Should not return 400 (validation error) - may return 404 (not found) which is OK
            response = client.get(f"/projects/{name}")
            assert response.status_code != 400, f"Valid name rejected: {name}"

    def test_empty_names_rejected(self):
        """Test that empty project/run names are handled properly."""
        client = TestClient(app)

        # Empty strings in URL path result in 404 (route not found)
        response = client.get("/projects//runs/test")
        assert response.status_code == 404

        response = client.get("/projects/test/runs//metrics")
        assert response.status_code == 404


class TestArtifactDownloadSecurity:
    """Security tests specific to artifact download endpoint."""

    def test_path_traversal_in_artifact_download(self):
        """Test path traversal protection in artifact download."""
        client = TestClient(app)

        # Path traversal attempts
        response = client.get("/api/projects/../../../etc/runs/passwd/artifacts/download")
        assert response.status_code in [400, 404]

        response = client.get("/api/projects/test/runs/..%2F..%2Fetc/artifacts/download")
        assert response.status_code in [400, 404]

    def test_invalid_characters_in_artifact_download(self):
        """Test that invalid characters are rejected in artifact download."""
        client = TestClient(app)

        response = client.get("/api/projects/project%20space/runs/run/artifacts/download")
        assert response.status_code == 400
        data = response.json()
        assert "Invalid project name" in data["detail"]


class TestMetadataSecurityEndpoints:
    """Security tests for metadata endpoints."""

    def test_path_traversal_in_metadata_get(self):
        """Test path traversal protection in metadata get."""
        client = TestClient(app)

        # Project metadata
        response = client.get("/api/projects/../../../etc/metadata")
        assert response.status_code in [400, 404]

        # Run metadata
        response = client.get("/api/projects/test/runs/../../../etc/metadata")
        assert response.status_code in [400, 404]

    def test_path_traversal_in_metadata_update(self):
        """Test path traversal protection in metadata update."""
        client = TestClient(app)

        payload = {"memo": "test"}

        # Project metadata
        response = client.put("/api/projects/../../../etc/metadata", json=payload)
        assert response.status_code in [400, 404]

        # Run metadata
        response = client.put("/api/projects/test/runs/../../../etc/metadata", json=payload)
        assert response.status_code in [400, 404]


class TestDeleteEndpointSecurity:
    """Security tests for delete endpoints."""

    def test_path_traversal_in_delete_project(self):
        """Test path traversal protection in project deletion."""
        client = TestClient(app)

        response = client.delete("/api/projects/../../../etc/passwd")
        assert response.status_code in [400, 404]

    def test_path_traversal_in_delete_run(self):
        """Test path traversal protection in run deletion."""
        client = TestClient(app)

        response = client.delete("/api/projects/test/runs/../../../etc/passwd")
        assert response.status_code in [400, 404]

    def test_special_characters_rejected_in_delete(self):
        """Test that special characters are rejected in delete endpoints."""
        client = TestClient(app)

        # Delete project with spaces
        response = client.delete("/api/projects/project%20with%20spaces")
        assert response.status_code == 400
        data = response.json()
        assert "Invalid project name" in data["detail"]

        # Delete run with spaces
        response = client.delete("/api/projects/test_project/runs/run%20with%20spaces")
        assert response.status_code == 400
        data = response.json()
        assert "Invalid" in data["detail"]
