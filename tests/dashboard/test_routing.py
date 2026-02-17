"""
Test routing behavior to ensure correct endpoint matching.
"""


class TestRoutingPriority:
    """Test that routes are matched in the correct order."""

    def test_project_runs_route_works(self, test_client, setup_test_data):
        """Test that project runs list route works correctly."""

        response = test_client.get("/projects/test_project")

        assert response.status_code == 200
        content = response.text

        # Should contain runs list content
        assert "Runs" in content or "run_1" in content

    def test_run_detail_route_with_actual_run(self, test_client, setup_test_data):
        """Test that run detail route works for actual run names."""

        response = test_client.get("/projects/test_project/runs/run_1")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        content = response.text
        # Should contain run detail specific content
        assert "run_1" in content

    def test_run_detail_route_nonexistent_run(self, test_client, setup_test_data):
        """Test that nonexistent run returns 404."""

        response = test_client.get("/projects/test_project/runs/nonexistent_run")

        assert response.status_code == 404

    def test_route_specificity_order(self, test_client, setup_test_data):
        """Test that more specific routes take precedence over less specific ones."""

        # Test run detail route
        response = test_client.get("/projects/test_project/runs/run_1")
        assert response.status_code == 200
        assert "run_1" in response.text


class TestEdgeCases:
    """Test edge cases in routing."""

    def test_nonexistent_project(self, test_client, setup_test_data):
        """Test that nonexistent project returns 404."""

        response = test_client.get("/projects/nonexistent/runs/run_1")
        assert response.status_code == 404
