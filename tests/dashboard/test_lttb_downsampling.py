"""Tests for LTTB downsampling functionality."""

import sys
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from aspara import Run
from aspara.dashboard.main import app
from aspara.dashboard.router import configure_data_dir


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest_asyncio.fixture
async def client(temp_data_dir):
    """Create test client with initialized services."""
    configure_data_dir(temp_data_dir)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestLTTBDownsampling:
    """Test suite for LTTB downsampling functionality."""

    @pytest.mark.asyncio
    async def test_small_dataset_no_downsampling(self, client, temp_data_dir):
        """Test that small datasets are not downsampled."""
        # Create a run with 100 metrics (below default threshold of 100000)
        run = Run(project="test_project", name="small_run", dir=temp_data_dir)

        for i in range(100):
            run.log({"loss": float(i)}, step=i)

        run.finish()

        # Fetch metrics via bulk API
        response = await client.get("/api/projects/test_project/runs/metrics?runs=small_run")
        assert response.status_code == 200

        data = response.json()
        # Bulk format: {"project": str, "metrics": {metric_name: {run_name: {...}}}}
        assert "metrics" in data
        assert "loss" in data["metrics"]
        assert "small_run" in data["metrics"]["loss"]
        assert len(data["metrics"]["loss"]["small_run"]["values"]) == 100  # No downsampling should occur

    @pytest.mark.asyncio
    async def test_large_dataset_with_downsampling(self, client, temp_data_dir, monkeypatch):
        """Test that large datasets are downsampled."""
        # Set a low threshold for testing (10 points)
        monkeypatch.setenv("ASPARA_LTTB_THRESHOLD", "10")

        # Force reload of config by clearing cached limits
        config_module = sys.modules["aspara.config"]
        config_module._resource_limits = None

        # Recreate services with new config
        configure_data_dir(temp_data_dir)

        # Create a run with 1000 metrics (above threshold of 10)
        run = Run(project="test_project", name="large_run", dir=temp_data_dir)

        for i in range(1000):
            run.log({"loss": float(i)}, step=i)

        run.finish()

        # Fetch metrics via bulk API
        response = await client.get("/api/projects/test_project/runs/metrics?runs=large_run")
        assert response.status_code == 200

        data = response.json()

        # Bulk format: {"project": str, "metrics": {metric_name: {run_name: {...}}}}
        assert "metrics" in data
        assert "loss" in data["metrics"]
        assert "large_run" in data["metrics"]["loss"]

        run_metrics = data["metrics"]["loss"]["large_run"]
        # Should be downsampled to threshold (10 points)
        assert len(run_metrics["values"]) <= 10
        assert len(run_metrics["steps"]) <= 10
        assert len(run_metrics["timestamps"]) <= 10

    @pytest.mark.asyncio
    async def test_multiple_metrics_downsampling(self, client, temp_data_dir, monkeypatch):
        """Test downsampling with multiple metric series."""
        # Set a low threshold for testing
        monkeypatch.setenv("ASPARA_LTTB_THRESHOLD", "10")

        # Force reload of config by clearing cached limits
        config_module = sys.modules["aspara.config"]
        config_module._resource_limits = None

        # Recreate services with new config
        configure_data_dir(temp_data_dir)

        # Create a run with multiple metrics
        run = Run(project="test_project", name="multi_metric_run", dir=temp_data_dir)

        for i in range(1000):
            run.log({"loss": float(i), "accuracy": float(100 - i / 10)}, step=i)

        run.finish()

        # Fetch metrics via bulk API
        response = await client.get("/api/projects/test_project/runs/metrics?runs=multi_metric_run")
        assert response.status_code == 200

        data = response.json()

        # Bulk format: {"project": str, "metrics": {metric_name: {run_name: {...}}}}
        assert "metrics" in data
        assert "loss" in data["metrics"], "Loss metric should be present"
        assert "accuracy" in data["metrics"], "Accuracy metric should be present"

        # Each metric is downsampled independently to threshold (10 points)
        assert len(data["metrics"]["loss"]["multi_metric_run"]["values"]) <= 10
        assert len(data["metrics"]["accuracy"]["multi_metric_run"]["values"]) <= 10

    @pytest.mark.asyncio
    async def test_empty_metrics(self, client, temp_data_dir):
        """Test that empty metrics are handled correctly."""
        # Create a run with no metrics
        run = Run(project="test_project", name="empty_run", dir=temp_data_dir)
        run.finish()

        # Fetch metrics via bulk API
        response = await client.get("/api/projects/test_project/runs/metrics?runs=empty_run")
        assert response.status_code == 200

        data = response.json()
        # Bulk format returns {"project": str, "metrics": {}}
        assert "metrics" in data
        assert len(data["metrics"]) == 0

    @pytest.mark.asyncio
    async def test_downsampling_preserves_shape(self, client, temp_data_dir, monkeypatch):
        """Test that downsampling preserves overall shape of data."""
        # Set a low threshold for testing
        monkeypatch.setenv("ASPARA_LTTB_THRESHOLD", "50")

        # Force reload of config by clearing cached limits
        config_module = sys.modules["aspara.config"]
        config_module._resource_limits = None

        # Recreate services with new config
        configure_data_dir(temp_data_dir)

        # Create a run with a sine wave pattern
        import math

        run = Run(project="test_project", name="sine_run", dir=temp_data_dir)

        for i in range(1000):
            value = math.sin(i / 50.0)  # Sine wave with period of ~314 steps
            run.log({"value": value}, step=i)

        run.finish()

        # Fetch metrics via bulk API
        response = await client.get("/api/projects/test_project/runs/metrics?runs=sine_run")
        assert response.status_code == 200

        data = response.json()

        # Bulk format: {"project": str, "metrics": {metric_name: {run_name: {...}}}}
        assert "metrics" in data
        assert "value" in data["metrics"]

        # Should be downsampled to ~50 points
        values = data["metrics"]["value"]["sine_run"]["values"]
        assert len(values) <= 50

        # Check that we still have both positive and negative values (sine wave shape)
        assert any(v > 0.5 for v in values), "Should have high positive values"
        assert any(v < -0.5 for v in values), "Should have high negative values"
