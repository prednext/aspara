"""
Tests for chart rendering functionality to reproduce and fix chart display errors.
"""

import tempfile

import pytest
from fastapi.testclient import TestClient

from aspara.dashboard.main import app


@pytest.fixture
def sample_metrics_data():
    """Sample metrics data that matches the real API response structure."""
    return [
        {
            "type": "params",
            "timestamp": "2025-06-13T17:18:25.064369",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": None,
            "metrics": None,
            "params": {"learning_rate": 0.01, "batch_size": 32, "optimizer": "adam", "model_type": "mlp"},
        },
        {
            "type": "artifact",
            "timestamp": "2025-06-13T17:18:25.065005",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": None,
            "metrics": None,
            "params": None,
        },
        {
            "type": "metrics",
            "timestamp": "2025-06-13T17:18:25.065724",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": 0,
            "metrics": {"train_loss": 1.0, "train_accuracy": 0.5, "val_loss": 1.07, "val_accuracy": 0.48},
            "params": None,
        },
        {
            "type": "metrics",
            "timestamp": "2025-06-13T17:18:25.166045",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": 1,
            "metrics": {
                "train_loss": 0.5841470984807897,
                "train_accuracy": 0.616631800693227,
                "val_loss": 0.6449531445981526,
                "val_accuracy": 0.588217090845148,
            },
            "params": None,
        },
        {
            "type": "metrics",
            "timestamp": "2025-06-13T17:18:25.266622",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": 2,
            "metrics": {
                "train_loss": 0.4242630760159015,
                "train_accuracy": 0.7030347637576881,
                "val_loss": 0.46594013928495864,
                "val_accuracy": 0.6739417894894313,
            },
            "params": None,
        },
    ]


@pytest.fixture
def temp_logs_dir():
    """Create a temporary logs directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def client(temp_logs_dir):
    """Create test client with temporary logs directory."""
    # Initialize services with temp directory
    from aspara.dashboard.router import configure_data_dir

    configure_data_dir(temp_logs_dir)

    return TestClient(app)


def test_processMetricsData_with_real_data():
    """Test the processMetricsData function with real API response data."""

    # Simulate the JavaScript processMetricsData function in Python
    def process_metrics_data_python(metrics):
        metrics_by_name = {}

        if not metrics or not isinstance(metrics, list):
            return metrics_by_name

        for index, entry in enumerate(metrics):
            if not entry or entry.get("type") != "metrics":
                continue

            # Additional check for null/undefined metrics field
            if not entry.get("metrics") or not isinstance(entry.get("metrics"), dict):
                continue

            step = entry.get("step", index)

            try:
                for name, value in entry["metrics"].items():
                    if value is None:
                        continue

                    # Handle numeric conversion more carefully
                    if isinstance(value, int | float):
                        numeric_value = float(value)
                    elif isinstance(value, str):
                        if value.strip() == "":
                            continue
                        try:
                            numeric_value = float(value)
                        except ValueError:
                            continue
                    else:
                        continue

                    # Check for valid numbers (including zero and negative numbers)
                    if not (isinstance(numeric_value, int | float) and str(numeric_value) != "nan"):
                        continue

                    if name not in metrics_by_name:
                        metrics_by_name[name] = []
                    metrics_by_name[name].append({"step": step, "value": numeric_value})
            except (ValueError, TypeError):
                continue

        return metrics_by_name

    # Test data that matches the real API response
    sample_data = [
        {
            "type": "params",
            "timestamp": "2025-06-13T17:18:25.064369",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": None,
            "metrics": None,
            "params": {"learning_rate": 0.01},
        },
        {
            "type": "metrics",
            "timestamp": "2025-06-13T17:18:25.065724",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": 0,
            "metrics": {"train_loss": 1.0, "train_accuracy": 0.5, "val_loss": 1.07, "val_accuracy": 0.48},
            "params": None,
        },
        {
            "type": "metrics",
            "timestamp": "2025-06-13T17:18:25.166045",
            "run": "simple_training_with_artifacts",
            "project": "default",
            "step": 1,
            "metrics": {"train_loss": 0.584, "train_accuracy": 0.617, "val_loss": 0.645, "val_accuracy": 0.588},
            "params": None,
        },
    ]

    result = process_metrics_data_python(sample_data)

    # Should have 4 metrics
    assert len(result) == 4
    assert "train_loss" in result
    assert "train_accuracy" in result
    assert "val_loss" in result
    assert "val_accuracy" in result

    # Check train_loss data
    train_loss_data = result["train_loss"]
    assert len(train_loss_data) == 2
    assert train_loss_data[0]["step"] == 0
    assert train_loss_data[0]["value"] == 1.0
    assert train_loss_data[1]["step"] == 1
    assert train_loss_data[1]["value"] == 0.584


def test_processMetricsData_with_mixed_data():
    """Test with mixed data types that might cause the original error."""

    def process_metrics_data_python(metrics):
        metrics_by_name = {}

        if not metrics or not isinstance(metrics, list):
            return metrics_by_name

        for index, entry in enumerate(metrics):
            if not entry or entry.get("type") != "metrics":
                continue

            # Additional check for null/undefined metrics field
            if not entry.get("metrics") or not isinstance(entry.get("metrics"), dict):
                continue

            step = entry.get("step", index)

            try:
                for name, value in entry["metrics"].items():
                    if value is None:
                        continue

                    # Handle numeric conversion more carefully
                    if isinstance(value, int | float):
                        numeric_value = float(value)
                    elif isinstance(value, str):
                        if value.strip() == "":
                            continue
                        try:
                            numeric_value = float(value)
                        except ValueError:
                            continue
                    else:
                        continue

                    # Check for valid numbers (including zero and negative numbers)
                    if not (isinstance(numeric_value, int | float) and str(numeric_value) != "nan"):
                        continue

                    if name not in metrics_by_name:
                        metrics_by_name[name] = []
                    metrics_by_name[name].append({"step": step, "value": numeric_value})
            except (ValueError, TypeError):
                continue

        return metrics_by_name

    # Test data with problematic values that could cause "Cannot convert undefined or null to object"
    problematic_data = [
        {
            "type": "metrics",
            "step": 0,
            "metrics": {
                "valid_metric": 1.0,
                "null_metric": None,
                "undefined_metric": None,
                "string_metric": "not_a_number",
                "empty_string": "",
                "zero_metric": 0,
            },
        },
        {
            "type": "params",  # Should be skipped
            "metrics": {"should_skip": 1.0},
        },
        {
            "type": "metrics",
            "step": 1,
            "metrics": None,  # This could cause the error
        },
        {"type": "metrics", "step": 2, "metrics": {"another_valid": 2.5}},
    ]

    # This should not raise an error
    result = process_metrics_data_python(problematic_data)

    # Should only have valid metrics
    assert len(result) == 3  # valid_metric, another_valid, zero_metric
    assert "valid_metric" in result
    assert "another_valid" in result
    assert "zero_metric" in result

    # Check values
    assert result["valid_metric"][0]["value"] == 1.0
    assert result["another_valid"][0]["value"] == 2.5
    assert result["zero_metric"][0]["value"] == 0


def test_chart_data_processing_edge_cases():
    """Test edge cases that might cause chart rendering errors."""

    def process_metrics_data_python(metrics):
        metrics_by_name = {}

        if not metrics or not isinstance(metrics, list):
            return metrics_by_name

        for index, entry in enumerate(metrics):
            if not entry or entry.get("type") != "metrics":
                continue

            # Additional check for null/undefined metrics field
            if not entry.get("metrics") or not isinstance(entry.get("metrics"), dict):
                continue

            step = entry.get("step", index)

            try:
                for name, value in entry["metrics"].items():
                    if value is None:
                        continue

                    # Handle numeric conversion more carefully
                    if isinstance(value, int | float):
                        numeric_value = float(value)
                    elif isinstance(value, str):
                        if value.strip() == "":
                            continue
                        try:
                            numeric_value = float(value)
                        except ValueError:
                            continue
                    else:
                        continue

                    # Check for valid numbers (including zero and negative numbers)
                    if not (isinstance(numeric_value, int | float) and str(numeric_value) != "nan"):
                        continue

                    if name not in metrics_by_name:
                        metrics_by_name[name] = []
                    metrics_by_name[name].append({"step": step, "value": numeric_value})
            except (ValueError, TypeError):
                continue

        return metrics_by_name

    # Test edge cases
    edge_cases = [
        None,  # Null input
        [],  # Empty array
        "not_an_array",  # Wrong type
        [None],  # Array with null
        [{}],  # Array with empty object
        [{"type": "metrics"}],  # Missing metrics field
        [{"type": "metrics", "metrics": {}}],  # Empty metrics
    ]

    for case in edge_cases:
        # Should not raise errors
        result = process_metrics_data_python(case)
        assert isinstance(result, dict)
        assert len(result) == 0
