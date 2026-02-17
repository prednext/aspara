"""Test MessagePack API endpoint."""

import tempfile

import msgpack
import pytest
from fastapi.testclient import TestClient

from aspara.dashboard.main import app
from aspara.dashboard.router import configure_data_dir

client = TestClient(app)


class TestMessagePackEndpoint:
    """Test MessagePack endpoint for metrics API."""

    @pytest.fixture
    def setup_test_data(self):
        """Setup test environment with temporary directory and test data."""
        import aspara

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize services with temp directory
            configure_data_dir(data_dir=tmpdir)

            # Create test runs using aspara.init()
            for i, run_name in enumerate(["run_1", "run_2"]):
                run = aspara.init(
                    project="test_project",
                    name=run_name,
                    config={"lr": 0.001, "batch_size": 32},
                    storage_backend="polars",
                    dir=tmpdir,
                )

                # Log metrics
                run.log({"loss": 0.5 - i * 0.1, "accuracy": 0.8 + i * 0.05}, step=0)
                run.log({"loss": 0.3 - i * 0.1, "accuracy": 0.85 + i * 0.05}, step=1)
                run.log({"loss": 0.1 - i * 0.1, "accuracy": 0.9 + i * 0.05}, step=2)

                aspara.finish()

            # Re-initialize services after creating runs
            configure_data_dir(data_dir=tmpdir)

            yield tmpdir

    def test_msgpack_endpoint_returns_binary(self, setup_test_data):
        """Test that msgpack endpoint returns binary data."""
        response = client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2&format=msgpack")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-msgpack"

        # Verify it's binary data
        assert isinstance(response.content, bytes)
        assert len(response.content) > 0

    def test_msgpack_decode_structure(self, setup_test_data):
        """Test that msgpack data can be decoded and has correct structure."""
        response = client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2&format=msgpack")

        assert response.status_code == 200

        # Decode MessagePack
        data = msgpack.unpackb(response.content, raw=False)

        # Verify structure
        assert "project" in data
        assert "metrics" in data
        assert data["project"] == "test_project"

        # Verify metrics structure
        metrics = data["metrics"]
        assert "loss" in metrics
        assert "accuracy" in metrics

        # Verify run data
        assert "run_1" in metrics["loss"]
        assert "run_2" in metrics["loss"]

        # Verify data arrays
        run1_loss = metrics["loss"]["run_1"]
        assert "steps" in run1_loss
        assert "values" in run1_loss
        assert "timestamps" in run1_loss

    def test_msgpack_vs_json_equivalence(self, setup_test_data):
        """Test that msgpack and JSON endpoints return equivalent data."""
        # Get JSON response
        json_response = client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2")
        json_data = json_response.json()

        # Get MessagePack response
        msgpack_response = client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2&format=msgpack")
        msgpack_data = msgpack.unpackb(msgpack_response.content, raw=False)

        # Verify data is equivalent
        assert json_data["project"] == msgpack_data["project"]
        assert json_data["metrics"].keys() == msgpack_data["metrics"].keys()

        # Verify run names are the same
        for metric_name in json_data["metrics"]:
            assert json_data["metrics"][metric_name].keys() == msgpack_data["metrics"][metric_name].keys()

    def test_msgpack_size_smaller_than_json(self, setup_test_data):
        """Test that msgpack response is smaller than JSON response."""
        # Get JSON response
        json_response = client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2")
        json_size = len(json_response.content)

        # Get MessagePack response
        msgpack_response = client.get("/api/projects/test_project/runs/metrics?runs=run_1,run_2&format=msgpack")
        msgpack_size = len(msgpack_response.content)

        # MessagePack should be smaller
        print(f"JSON size: {json_size} bytes")
        print(f"MessagePack size: {msgpack_size} bytes")
        print(f"Reduction: {json_size - msgpack_size} bytes ({(1 - msgpack_size / json_size) * 100:.1f}%)")

        assert msgpack_size < json_size
        # Should be at least 10% smaller (small datasets have lower compression ratio)
        assert msgpack_size < json_size * 0.9

    def test_msgpack_error_handling(self, setup_test_data):
        """Test error handling for msgpack endpoint."""
        # Test with no runs parameter
        response = client.get("/api/projects/test_project/runs/metrics?runs=&format=msgpack")
        assert response.status_code == 400

        # Test with nonexistent run (returns empty metrics, not 404)
        response = client.get("/api/projects/test_project/runs/metrics?runs=nonexistent_run&format=msgpack")
        assert response.status_code == 200
        data = msgpack.unpackb(response.content, raw=False)
        # Should return empty metrics
        assert data["metrics"] == {}

    def test_msgpack_with_single_run(self, setup_test_data):
        """Test msgpack endpoint with single run."""
        response = client.get("/api/projects/test_project/runs/metrics?runs=run_1&format=msgpack")

        assert response.status_code == 200
        data = msgpack.unpackb(response.content, raw=False)

        assert data["project"] == "test_project"
        assert "metrics" in data
        assert "run_1" in data["metrics"]["loss"]
        assert "run_2" not in data["metrics"]["loss"]

    def test_msgpack_uses_float32_encoding(self, setup_test_data):
        """Test that msgpack endpoint uses float32 encoding for smaller payload.

        Note: We verify this by checking that all float values can be represented
        as float32 without precision loss, rather than counting raw bytes.
        The old approach of counting 0xCB bytes was flaky because 0xCB can appear
        in the byte representation of large integers (e.g., timestamps).
        """
        import struct

        response = client.get("/api/projects/test_project/runs/metrics?runs=run_1&format=msgpack")
        assert response.status_code == 200

        # Decode msgpack and collect all float values
        data = msgpack.unpackb(response.content, raw=False)

        floats_found = []

        def collect_floats(obj):
            if isinstance(obj, float):
                floats_found.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    collect_floats(v)
            elif isinstance(obj, list):
                for v in obj:
                    collect_floats(v)

        collect_floats(data)

        # Verify floats exist
        assert len(floats_found) > 0, "Expected float values in response"

        # Verify all floats can be represented as float32 without precision loss
        # (This is what use_single_float=True guarantees)
        for f in floats_found:
            # Round-trip through float32 should not change value significantly
            f32 = struct.unpack("f", struct.pack("f", f))[0]
            # Allow small relative error for non-zero values, absolute for near-zero
            if f != 0:
                relative_error = abs((f - f32) / f)
                assert relative_error < 1e-6, f"Value {f} lost precision in float32 round-trip"
            else:
                assert abs(f - f32) < 1e-6, f"Value {f} lost precision in float32 round-trip"

    def test_msgpack_float32_precision_sufficient(self, setup_test_data):
        """Test that float32 precision is sufficient for metrics visualization."""
        response = client.get("/api/projects/test_project/runs/metrics?runs=run_1&format=msgpack")
        assert response.status_code == 200

        data = msgpack.unpackb(response.content, raw=False)

        # Get original values logged in setup (loss: 0.5, 0.3, 0.1)
        loss_values = data["metrics"]["loss"]["run_1"]["values"]

        # float32 has ~7 significant digits precision
        # Our test values (0.5, 0.3, 0.1) should be very close
        expected_values = [0.5, 0.3, 0.1]
        for actual, expected in zip(loss_values, expected_values, strict=True):
            # Allow small float32 precision loss (1e-6 relative error)
            assert abs(actual - expected) < 1e-6, f"Float32 precision loss too large: {actual} vs {expected}"

    def test_msgpack_with_since_filter(self, setup_test_data):
        """Test msgpack endpoint with since parameter for delta fetching."""
        # Without since filter - should return all data
        response = client.get("/api/projects/test_project/runs/metrics?runs=run_1&format=msgpack")
        assert response.status_code == 200
        data = msgpack.unpackb(response.content, raw=False)
        assert len(data["metrics"]["loss"]["run_1"]["steps"]) == 3  # All 3 steps

        # With since filter set to far past (epoch) - should return all data
        response_past = client.get("/api/projects/test_project/runs/metrics?runs=run_1&format=msgpack&since=1000")
        assert response_past.status_code == 200
        data_past = msgpack.unpackb(response_past.content, raw=False)
        assert len(data_past["metrics"]["loss"]["run_1"]["steps"]) == 3

        # With since filter set to far future - should return no data
        future_timestamp = int((2100 * 365 * 24 * 60 * 60) * 1000)  # Year 2100 in Unix ms
        response_future = client.get(f"/api/projects/test_project/runs/metrics?runs=run_1&format=msgpack&since={future_timestamp}")
        assert response_future.status_code == 200
        data_future = msgpack.unpackb(response_future.content, raw=False)
        # With future timestamp, run should have no data or empty arrays
        if "loss" in data_future["metrics"] and "run_1" in data_future["metrics"]["loss"]:
            assert len(data_future["metrics"]["loss"]["run_1"]["steps"]) == 0
