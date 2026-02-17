"""
Tests for corrupted run detection and display functionality
"""


class TestCorruptedRuns:
    """Tests for corrupted run detection and display functionality"""

    def test_corrupted_runs_in_list(self, test_client, setup_test_data_with_corrupted):
        """Test that corrupted runs are displayed correctly in the list"""
        response = test_client.get("/projects/corrupted_project/runs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Verify that corrupted run names are displayed
        assert "corrupted_run_empty" in response.text

        # Verify that necessary CSS classes for corrupted run display are included
        # Note: Template uses text-status-error (custom color in Tailwind CSS v4)
        assert "bg-red-50" in response.text or "border-status-error" in response.text
        assert "text-status-error" in response.text or "Error" in response.text

    def test_corrupted_run_detail(self, test_client, setup_test_data_with_corrupted):
        """Test that corrupted run detail page is displayed correctly"""
        response = test_client.get("/projects/corrupted_project/runs/corrupted_run_empty")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
