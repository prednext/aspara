"""
CORS configuration tests for the main aspara server app.

Verifies that allow_credentials is disabled when allow_origins=["*"],
which is required to prevent CSRF / credential leakage per CORS spec.
"""

from starlette.testclient import TestClient

from aspara.server import app


class TestMainAppCORS:
    """Test CORS configuration on the main (combined) aspara app."""

    def test_credentials_not_allowed_with_wildcard_origin(self):
        """allow_credentials must be False when allow_origins=["*"].

        Returning 'true' here is a CORS spec violation and a security
        vulnerability that lets any website make credentialed requests.
        """
        client = TestClient(app)
        response = client.options(
            "/api/projects/test_project/runs/metrics",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Preflight should be handled by CORSMiddleware
        assert response.status_code in (200, 204)
        # The wildcard origin is reflected, but credentials must NOT be allowed
        assert response.headers.get("access-control-allow-credentials", "").lower() != "true"

    def test_wildcard_origin_allowed_without_credentials(self):
        """Wildcard origin should still be allowed (just without credentials)."""
        client = TestClient(app)
        # Use a non-existent endpoint - CORS headers are added by middleware
        # regardless of the response status, so a 404 is sufficient.
        response = client.get(
            "/nonexistent-endpoint-for-cors-test",
            headers={"Origin": "https://evil.example.com"},
        )
        # CORS header should be present even on 404
        allow_origin = response.headers.get("access-control-allow-origin", "")
        assert allow_origin in ("*", "https://evil.example.com")
        assert response.headers.get("access-control-allow-credentials", "").lower() != "true"
