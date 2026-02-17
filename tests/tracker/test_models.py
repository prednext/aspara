"""
Tests for Aspara tracker data models
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from aspara.models import MetricRecord
from aspara.tracker.models import (
    ArtifactUploadResponse,
    ConfigUpdateRequest,
    FinishRequest,
    HealthResponse,
    MetricsListResponse,
    MetricsResponse,
    ProjectsResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunsResponse,
    StatusResponse,
    SummaryUpdateRequest,
)

# ---------------------------------------------------------------------------
# MetricRecord tests
# ---------------------------------------------------------------------------


def test_metrics_data_model():
    """Test that MetricRecord model works correctly"""

    # Create model with valid data
    data = MetricRecord(metrics={"loss": 0.5, "accuracy": 0.8}, step=1)

    # Verify that basic attributes are set correctly
    assert data.metrics == {"loss": 0.5, "accuracy": 0.8}
    assert data.step == 1
    assert isinstance(data.timestamp, datetime)

    # Verify that JSON conversion works correctly
    json_data = data.model_dump()
    assert json_data["metrics"]["loss"] == 0.5


def test_metrics_data_validation():
    """Test that MetricRecord model validation works correctly"""

    # Verify that an error occurs when metrics are missing
    with pytest.raises(ValidationError):
        MetricRecord(
            # metrics are missing
        )

    # Verify that an error occurs when metrics are not a dictionary
    with pytest.raises(ValidationError):
        MetricRecord(
            metrics="not_a_dict",  # Not a dictionary
        )


def test_metrics_data_optional_fields():
    """Test that MetricRecord model optional fields work correctly"""

    # When step is omitted
    data = MetricRecord(metrics={"loss": 0.5})
    assert data.step is None


# ---------------------------------------------------------------------------
# HealthResponse / MetricsResponse / StatusResponse tests
# ---------------------------------------------------------------------------


class TestHealthResponse:
    def test_default_status(self):
        """Test that HealthResponse defaults to status 'ok'"""
        resp = HealthResponse()
        assert resp.status == "ok"

    def test_custom_status(self):
        """Test that HealthResponse accepts a custom status value"""
        resp = HealthResponse(status="degraded")
        assert resp.status == "degraded"


class TestMetricsResponse:
    def test_default_status(self):
        """Test that MetricsResponse defaults to status 'ok'"""
        resp = MetricsResponse()
        assert resp.status == "ok"


class TestStatusResponse:
    def test_default_status(self):
        """Test that StatusResponse defaults to status 'ok'"""
        resp = StatusResponse()
        assert resp.status == "ok"


# ---------------------------------------------------------------------------
# RunCreateRequest tests
# ---------------------------------------------------------------------------


class TestRunCreateRequest:
    def test_minimal_request(self):
        """Test that only name is required and other fields use defaults"""
        req = RunCreateRequest(name="run-1")
        assert req.name == "run-1"
        assert req.config == {}
        assert req.tags == []
        assert req.notes == ""
        assert req.project_tags is None

    def test_full_request(self):
        """Test that all fields can be explicitly specified"""
        req = RunCreateRequest(
            name="run-2",
            config={"lr": 0.01, "epochs": 10},
            tags=["baseline", "v1"],
            notes="initial experiment",
            project_tags=["dog", "cat"],
        )
        assert req.name == "run-2"
        assert req.config == {"lr": 0.01, "epochs": 10}
        assert req.tags == ["baseline", "v1"]
        assert req.notes == "initial experiment"
        assert req.project_tags == ["dog", "cat"]

    def test_name_is_required(self):
        """Test that omitting name raises a validation error"""
        with pytest.raises(ValidationError):
            RunCreateRequest()

    def test_config_accepts_nested_dict(self):
        """Test that config accepts nested dictionaries"""
        req = RunCreateRequest(name="run-3", config={"optimizer": {"type": "adam", "lr": 0.001}})
        assert req.config["optimizer"]["type"] == "adam"

    def test_project_tags_none_vs_empty(self):
        """Test that project_tags distinguishes None (default) from an empty list"""
        req_none = RunCreateRequest(name="run-4")
        req_empty = RunCreateRequest(name="run-5", project_tags=[])
        assert req_none.project_tags is None
        assert req_empty.project_tags == []


# ---------------------------------------------------------------------------
# RunCreateResponse tests
# ---------------------------------------------------------------------------


class TestRunCreateResponse:
    def test_required_fields(self):
        """Test that all required fields are set and status defaults to 'ok'"""
        resp = RunCreateResponse(project="my_project", name="run-1", run_id="abc123")
        assert resp.status == "ok"
        assert resp.project == "my_project"
        assert resp.name == "run-1"
        assert resp.run_id == "abc123"

    def test_missing_project_raises(self):
        """Test that omitting project raises a validation error"""
        with pytest.raises(ValidationError):
            RunCreateResponse(name="run-1", run_id="abc123")

    def test_missing_name_raises(self):
        """Test that omitting name raises a validation error"""
        with pytest.raises(ValidationError):
            RunCreateResponse(project="my_project", run_id="abc123")

    def test_missing_run_id_raises(self):
        """Test that omitting run_id raises a validation error"""
        with pytest.raises(ValidationError):
            RunCreateResponse(project="my_project", name="run-1")


# ---------------------------------------------------------------------------
# ArtifactUploadResponse tests
# ---------------------------------------------------------------------------


class TestArtifactUploadResponse:
    def test_required_fields(self):
        """Test that all required fields are set and status defaults to 'ok'"""
        resp = ArtifactUploadResponse(artifact_name="model.pt", file_size=1024)
        assert resp.status == "ok"
        assert resp.artifact_name == "model.pt"
        assert resp.file_size == 1024

    def test_missing_artifact_name_raises(self):
        """Test that omitting artifact_name raises a validation error"""
        with pytest.raises(ValidationError):
            ArtifactUploadResponse(file_size=1024)

    def test_missing_file_size_raises(self):
        """Test that omitting file_size raises a validation error"""
        with pytest.raises(ValidationError):
            ArtifactUploadResponse(artifact_name="model.pt")


# ---------------------------------------------------------------------------
# ConfigUpdateRequest tests
# ---------------------------------------------------------------------------


class TestConfigUpdateRequest:
    def test_default_empty_config(self):
        """Test that config defaults to an empty dict when omitted"""
        req = ConfigUpdateRequest()
        assert req.config == {}

    def test_with_config(self):
        """Test that config accepts arbitrary key-value pairs"""
        req = ConfigUpdateRequest(config={"lr": 0.001, "batch_size": 32})
        assert req.config["lr"] == 0.001
        assert req.config["batch_size"] == 32


# ---------------------------------------------------------------------------
# SummaryUpdateRequest tests
# ---------------------------------------------------------------------------


class TestSummaryUpdateRequest:
    def test_default_empty_summary(self):
        """Test that summary defaults to an empty dict when omitted"""
        req = SummaryUpdateRequest()
        assert req.summary == {}

    def test_with_summary(self):
        """Test that summary accepts arbitrary key-value pairs"""
        req = SummaryUpdateRequest(summary={"best_loss": 0.05, "best_accuracy": 0.98})
        assert req.summary["best_loss"] == 0.05
        assert req.summary["best_accuracy"] == 0.98


# ---------------------------------------------------------------------------
# FinishRequest tests
# ---------------------------------------------------------------------------


class TestFinishRequest:
    def test_default_exit_code(self):
        """Test that exit_code defaults to 0 (success)"""
        req = FinishRequest()
        assert req.exit_code == 0

    def test_custom_exit_code(self):
        """Test that a non-zero exit_code can be set"""
        req = FinishRequest(exit_code=1)
        assert req.exit_code == 1

    def test_negative_exit_code(self):
        """Test that a negative exit_code is accepted"""
        req = FinishRequest(exit_code=-1)
        assert req.exit_code == -1


# ---------------------------------------------------------------------------
# MetricsListResponse / ProjectsResponse / RunsResponse tests
# ---------------------------------------------------------------------------


class TestMetricsListResponse:
    def test_with_metrics(self):
        """Test that metrics list holds the provided entries"""
        resp = MetricsListResponse(metrics=[{"loss": 0.5}, {"loss": 0.3}])
        assert len(resp.metrics) == 2

    def test_empty_metrics(self):
        """Test that an empty metrics list is accepted"""
        resp = MetricsListResponse(metrics=[])
        assert resp.metrics == []

    def test_metrics_is_required(self):
        """Test that omitting metrics raises a validation error"""
        with pytest.raises(ValidationError):
            MetricsListResponse()


class TestProjectsResponse:
    def test_with_projects(self):
        """Test that projects list holds the provided names"""
        resp = ProjectsResponse(projects=["proj_a", "proj_b"])
        assert resp.projects == ["proj_a", "proj_b"]

    def test_empty_projects(self):
        """Test that an empty projects list is accepted"""
        resp = ProjectsResponse(projects=[])
        assert resp.projects == []

    def test_projects_is_required(self):
        """Test that omitting projects raises a validation error"""
        with pytest.raises(ValidationError):
            ProjectsResponse()


class TestRunsResponse:
    def test_with_runs(self):
        """Test that runs list holds the provided names"""
        resp = RunsResponse(runs=["run-1", "run-2"])
        assert resp.runs == ["run-1", "run-2"]

    def test_empty_runs(self):
        """Test that an empty runs list is accepted"""
        resp = RunsResponse(runs=[])
        assert resp.runs == []

    def test_runs_is_required(self):
        """Test that omitting runs raises a validation error"""
        with pytest.raises(ValidationError):
            RunsResponse()


# ---------------------------------------------------------------------------
# Serialization round-trip tests
# ---------------------------------------------------------------------------


class TestModelSerialization:
    def test_run_create_request_round_trip(self):
        """Test that model_dump and reconstruction produce an identical object"""
        original = RunCreateRequest(
            name="run-1",
            config={"lr": 0.01},
            tags=["v1"],
            notes="test",
            project_tags=["cat"],
        )
        dumped = original.model_dump()
        restored = RunCreateRequest(**dumped)
        assert restored == original

    def test_run_create_response_json_round_trip(self):
        """Test round-trip through JSON string serialization"""
        original = RunCreateResponse(project="proj", name="run-1", run_id="abc")
        json_str = original.model_dump_json()
        restored = RunCreateResponse.model_validate_json(json_str)
        assert restored == original

    def test_artifact_upload_response_round_trip(self):
        """Test that model_dump and reconstruction produce an identical object"""
        original = ArtifactUploadResponse(artifact_name="data.csv", file_size=2048)
        dumped = original.model_dump()
        restored = ArtifactUploadResponse(**dumped)
        assert restored == original
