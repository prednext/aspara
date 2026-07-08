"""
Tests verifying that the main server app does not expose CORS headers.

The dashboard static JS and API are same-origin, and the tracker API is
consumed by the Python SDK, so CORS is intentionally disabled. Returning
CORS allow headers would let cross-origin sites pass the X-Requested-With
CSRF header check via preflight, defeating that protection.
"""

from starlette.testclient import TestClient

from aspara.server import app


class TestMainAppNoCors:
    """Test that CORS middleware is not enabled on the main aspara app."""

    def test_preflight_does_not_return_cors_headers(self):
        """A cross-origin preflight should not receive CORS allow headers."""
        client = TestClient(app)
        response = client.options(
            "/api/projects/test_project/runs/metrics",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-headers" not in response.headers

    def test_actual_request_does_not_return_cors_headers(self):
        """A cross-origin GET should not receive CORS allow headers."""
        client = TestClient(app)
        response = client.get(
            "/api/projects/test_project/runs/metrics",
            headers={"Origin": "https://evil.example.com"},
        )
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-credentials" not in response.headers
