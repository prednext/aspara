"""
Tests for Aspara tracker API endpoints
"""

import io
import json

import pytest
from fastapi.testclient import TestClient

from aspara.tracker.main import app

# CSRF protection header required for all POST requests
CSRF_HEADER = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture
def test_client_with_real_storage(tmp_path, monkeypatch):
    """Fixture to provide test client with real storage"""
    # Set data directory with environment variable
    monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

    client = TestClient(app)
    yield client, tmp_path


@pytest.fixture
def test_client():
    """Fixture to provide simple test client"""
    client = TestClient(app)
    yield client


def test_health_check(test_client):
    """Test that health check endpoint works correctly"""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_save_metrics(test_client_with_real_storage):
    """Test that metrics save endpoint works correctly"""
    client, tmp_path = test_client_with_real_storage

    data = {
        "metrics": {"loss": 0.5, "accuracy": 0.8},
        "step": 1,
    }

    response = client.post("/api/v1/projects/test_project/runs/test_run_1/metrics", json=data, headers=CSRF_HEADER)

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "ok"

    run_file = tmp_path / "test_project" / "test_run_1.jsonl"
    assert run_file.exists()


class TestTrackerAPIIntegration:
    """Integration tests using real services and storage (no mocks).

    These tests use actual JsonlMetricsStorage to verify that the API
    correctly integrates with the storage layer and performs real
    file operations.
    """

    def test_save_and_retrieve_metrics_integration(self, tmp_path, monkeypatch):
        """Test that metrics can be saved and retrieved using real storage."""
        # Set data directory with environment variable
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        # Create test client
        client = TestClient(app)

        # Save metrics
        metrics_data = {
            "metrics": {"loss": 0.5, "accuracy": 0.8},
            "step": 1,
        }

        response = client.post("/api/v1/projects/test_project/runs/test_run/metrics", json=metrics_data, headers=CSRF_HEADER)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "ok"

        # Verify file was actually created
        run_file = tmp_path / "test_project" / "test_run.jsonl"
        assert run_file.exists()

        # Verify file content
        with run_file.open(encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["metrics"]["loss"] == 0.5
            assert data["metrics"]["accuracy"] == 0.8

    def test_multiple_metrics_same_run_integration(self, tmp_path, monkeypatch):
        """Test that multiple metrics can be saved to the same run."""
        # Set data directory with environment variable
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        # Save multiple metrics to the same run
        for step in range(3):
            metrics_data = {
                "metrics": {"loss": 1.0 - step * 0.3, "accuracy": step * 0.3},
                "step": step,
            }
            response = client.post("/api/v1/projects/multi_project/runs/multi_run/metrics", json=metrics_data, headers=CSRF_HEADER)
            assert response.status_code == 200

        # Verify file contains all metrics
        run_file = tmp_path / "multi_project" / "multi_run.jsonl"
        assert run_file.exists()

        with run_file.open(encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 3  # 3 metrics entries

            # Verify each metric entry
            for i, line in enumerate(lines):
                data = json.loads(line)
                assert data["step"] == i
                assert "loss" in data["metrics"]
                assert "accuracy" in data["metrics"]

    def test_run_creation_with_project_tags_updates_project_metadata(self, tmp_path, monkeypatch):
        """Run creation with project_tags should write project-level metadata.json with tags."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "run1"

        response = client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {"lr": 0.01},
                "tags": ["baseline"],
                "notes": "first run",
                "project_tags": ["dog", "cat"],
            },
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["project"] == project
        assert data["name"] == run_name

        project_metadata_path = tmp_path / project / "metadata.json"
        assert project_metadata_path.exists()

        with project_metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        assert metadata["tags"] == ["dog", "cat"]
        assert metadata["created_at"] is not None
        assert metadata["updated_at"] is not None

    def test_multiple_run_creations_merge_project_tags_and_preserve_created_at(self, tmp_path, monkeypatch):
        """Multiple run creations with project_tags should merge tags and keep created_at stable."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"

        # First run
        response1 = client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": "run1",
                "config": {},
                "tags": [],
                "notes": "first run",
                "project_tags": ["dog", "cat"],
            },
            headers=CSRF_HEADER,
        )
        assert response1.status_code == 200

        project_metadata_path = tmp_path / project / "metadata.json"
        assert project_metadata_path.exists()

        with project_metadata_path.open(encoding="utf-8") as f:
            first_metadata = json.load(f)

        first_created_at = first_metadata["created_at"]
        first_updated_at = first_metadata["updated_at"]
        assert first_metadata["tags"] == ["dog", "cat"]

        # Second run with overlapping and new tags
        response2 = client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": "run2",
                "config": {},
                "tags": [],
                "notes": "second run",
                "project_tags": ["cat", "rabbit"],
            },
            headers=CSRF_HEADER,
        )
        assert response2.status_code == 200

        with project_metadata_path.open(encoding="utf-8") as f:
            second_metadata = json.load(f)

        assert second_metadata["created_at"] == first_created_at
        assert second_metadata["updated_at"] != first_updated_at
        assert second_metadata["tags"] == ["dog", "cat", "rabbit"]

    def test_duplicate_run_creation_returns_conflict(self, tmp_path, monkeypatch):
        """Creating a run with an existing name should return 409 Conflict."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "run1"

        payload = {
            "name": run_name,
            "config": {},
            "tags": [],
            "notes": "first run",
            "project_tags": ["dog"],
        }

        # First creation should succeed
        response1 = client.post(f"/api/v1/projects/{project}/runs", json=payload, headers=CSRF_HEADER)
        assert response1.status_code == 200

        # Second creation with same name should return 409
        response2 = client.post(f"/api/v1/projects/{project}/runs", json=payload, headers=CSRF_HEADER)
        assert response2.status_code == 409
        data = response2.json()
        assert data["detail"] == "Run already exists"

    def test_upload_artifact_basic(self, tmp_path, monkeypatch):
        """Test basic artifact upload functionality."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Upload artifact
        test_content = b"test artifact content"
        files = {"file": ("test_artifact.txt", io.BytesIO(test_content), "text/plain")}

        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/artifacts",
            files=files,
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["artifact_name"] == "test_artifact.txt"
        assert data["file_size"] == len(test_content)

        # Verify file was saved
        artifact_path = tmp_path / project / run_name / "artifacts" / "test_artifact.txt"
        assert artifact_path.exists()
        assert artifact_path.read_bytes() == test_content

        # Verify metadata was updated
        metadata_path = tmp_path / project / f"{run_name}.meta.json"
        assert metadata_path.exists()
        with metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        artifacts = metadata.get("artifacts", [])
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "test_artifact.txt"
        assert artifacts[0]["file_size"] == len(test_content)

    def test_upload_artifact_with_custom_name(self, tmp_path, monkeypatch):
        """Test artifact upload with custom name."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Upload artifact with custom name
        test_content = b"test content"
        files = {"file": ("original.txt", io.BytesIO(test_content), "text/plain")}
        data = {"name": "custom_name.txt"}

        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/artifacts",
            files=files,
            data=data,
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["artifact_name"] == "custom_name.txt"

        # Verify file was saved with custom name
        artifact_path = tmp_path / project / run_name / "artifacts" / "custom_name.txt"
        assert artifact_path.exists()

    def test_upload_artifact_with_description_and_category(self, tmp_path, monkeypatch):
        """Test artifact upload with description and category."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Upload artifact with description and category
        test_content = b"model weights"
        files = {"file": ("model.pth", io.BytesIO(test_content), "application/octet-stream")}
        data = {
            "description": "Trained model weights",
            "category": "model",
        }

        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/artifacts",
            files=files,
            data=data,
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200

        # Verify metadata includes description and category
        metadata_path = tmp_path / project / f"{run_name}.meta.json"
        with metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        artifacts = metadata.get("artifacts", [])
        assert len(artifacts) == 1
        assert artifacts[0]["description"] == "Trained model weights"
        assert artifacts[0]["category"] == "model"

    def test_upload_artifact_invalid_category(self, tmp_path, monkeypatch):
        """Test artifact upload with invalid category."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Upload artifact with invalid category
        test_content = b"test content"
        files = {"file": ("test.txt", io.BytesIO(test_content), "text/plain")}
        data = {"category": "invalid_category"}

        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/artifacts",
            files=files,
            data=data,
            headers=CSRF_HEADER,
        )

        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]

    def test_update_config(self, tmp_path, monkeypatch):
        """Test updating config for an existing run."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {"lr": 0.01},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Update config
        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/config",
            json={"config": {"lr": 0.001, "batch_size": 32}},
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify metadata was updated
        metadata_path = tmp_path / project / f"{run_name}.meta.json"
        with metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        assert metadata["config"]["lr"] == 0.001
        assert metadata["config"]["batch_size"] == 32

    def test_update_config_nonexistent_run(self, tmp_path, monkeypatch):
        """Test updating config for a nonexistent run returns 404."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        response = client.post(
            "/api/v1/projects/test_project/runs/nonexistent/config",
            json={"config": {"lr": 0.001}},
            headers=CSRF_HEADER,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_update_summary(self, tmp_path, monkeypatch):
        """Test updating summary for an existing run."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Update summary
        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/summary",
            json={"summary": {"best_loss": 0.05, "best_accuracy": 0.98}},
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify metadata was updated
        metadata_path = tmp_path / project / f"{run_name}.meta.json"
        with metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        assert metadata["summary"]["best_loss"] == 0.05
        assert metadata["summary"]["best_accuracy"] == 0.98

    def test_update_summary_nonexistent_run(self, tmp_path, monkeypatch):
        """Test updating summary for a nonexistent run returns 404."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        response = client.post(
            "/api/v1/projects/test_project/runs/nonexistent/summary",
            json={"summary": {"best_loss": 0.05}},
            headers=CSRF_HEADER,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_finish_run_success(self, tmp_path, monkeypatch):
        """Test finishing a run with exit_code=0."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Finish run
        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/finish",
            json={"exit_code": 0},
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify metadata was updated
        metadata_path = tmp_path / project / f"{run_name}.meta.json"
        with metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        assert metadata["exit_code"] == 0
        assert "finish_time" in metadata
        assert metadata["finish_time"] is not None

    def test_finish_run_failure(self, tmp_path, monkeypatch):
        """Test finishing a run with non-zero exit_code."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        project = "test_project"
        run_name = "test_run"

        # Create run first
        client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {},
                "tags": [],
                "notes": "",
            },
            headers=CSRF_HEADER,
        )

        # Finish run with error
        response = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/finish",
            json={"exit_code": 1},
            headers=CSRF_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify metadata was updated with error exit code
        metadata_path = tmp_path / project / f"{run_name}.meta.json"
        with metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        assert metadata["exit_code"] == 1
        assert "finish_time" in metadata

    def test_finish_nonexistent_run(self, tmp_path, monkeypatch):
        """Test finishing a nonexistent run returns 404."""
        monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))

        client = TestClient(app)

        response = client.post(
            "/api/v1/projects/test_project/runs/nonexistent/finish",
            json={"exit_code": 0},
            headers=CSRF_HEADER,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"


class TestExperimentLifecycle:
    """End-to-end tests that simulate a complete experiment run.

    These tests mimic the flow of a real training script calling the tracker
    API: create run, log metrics during training, update config, upload
    artifacts, update summary, and finish. They verify that all data persists
    correctly across the full lifecycle.
    """

    def test_full_experiment_lifecycle_success(self, test_client_with_real_storage):
        """Test complete experiment flow: create -> metrics -> config -> summary -> finish."""
        client, tmp_path = test_client_with_real_storage

        project = "mnist_classifier"
        run_name = "exp_001"

        # Step 1: Create run
        create_resp = client.post(
            f"/api/v1/projects/{project}/runs",
            json={
                "name": run_name,
                "config": {"lr": 0.01, "batch_size": 64},
                "tags": ["baseline", "v1"],
                "notes": "Initial experiment",
                "project_tags": ["mnist", "classification"],
            },
            headers=CSRF_HEADER,
        )
        assert create_resp.status_code == 200, f"Create run failed: {create_resp.text}"
        create_data = create_resp.json()
        assert create_data["status"] == "ok"
        assert create_data["project"] == project
        assert create_data["name"] == run_name
        run_id = create_data["run_id"]
        assert len(run_id) == 16

        # Step 2: Simulate training loop - save metrics at each step
        num_steps = 5
        for step in range(num_steps):
            metrics_resp = client.post(
                f"/api/v1/projects/{project}/runs/{run_name}/metrics",
                json={
                    "metrics": {
                        "loss": 1.0 - step * 0.15,
                        "accuracy": step * 0.2,
                    },
                    "step": step,
                },
                headers=CSRF_HEADER,
            )
            assert metrics_resp.status_code == 200, f"Metrics save failed at step {step}: {metrics_resp.text}"

        # Step 3: Update config mid-run (e.g., learning rate schedule)
        config_resp = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/config",
            json={"config": {"lr_decayed": 0.005, "epoch": 1}},
            headers=CSRF_HEADER,
        )
        assert config_resp.status_code == 200, f"Config update failed: {config_resp.text}"

        # Step 4: Upload artifact (e.g., checkpoint)
        checkpoint_content = b"fake_model_weights_binary"
        files = {"file": ("checkpoint.pt", io.BytesIO(checkpoint_content), "application/octet-stream")}
        artifact_resp = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/artifacts",
            files=files,
            data={"description": "Best checkpoint", "category": "model"},
            headers=CSRF_HEADER,
        )
        assert artifact_resp.status_code == 200, f"Artifact upload failed: {artifact_resp.text}"
        assert artifact_resp.json()["artifact_name"] == "checkpoint.pt"

        # Step 5: Update summary with final results
        summary_resp = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/summary",
            json={"summary": {"best_loss": 0.25, "best_accuracy": 0.95, "total_steps": num_steps}},
            headers=CSRF_HEADER,
        )
        assert summary_resp.status_code == 200, f"Summary update failed: {summary_resp.text}"

        # Step 6: Finish run successfully
        finish_resp = client.post(
            f"/api/v1/projects/{project}/runs/{run_name}/finish",
            json={"exit_code": 0},
            headers=CSRF_HEADER,
        )
        assert finish_resp.status_code == 200, f"Finish run failed: {finish_resp.text}"

        # Verify all persisted data
        base = tmp_path / project

        # Metrics file
        metrics_file = base / f"{run_name}.jsonl"
        assert metrics_file.exists()
        with metrics_file.open(encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == num_steps
        for i, line in enumerate(lines):
            record = json.loads(line)
            assert record["step"] == i
            expected_loss = 1.0 - i * 0.15
            expected_accuracy = i * 0.2
            assert record["metrics"]["loss"] == pytest.approx(expected_loss)
            assert record["metrics"]["accuracy"] == pytest.approx(expected_accuracy)

        # Metadata file
        meta_file = base / f"{run_name}.meta.json"
        assert meta_file.exists()
        with meta_file.open(encoding="utf-8") as f:
            meta = json.load(f)

        assert meta["run_id"] == run_id
        assert meta["tags"] == ["baseline", "v1"]
        assert meta["notes"] == "Initial experiment"
        assert meta["config"]["lr"] == 0.01
        assert meta["config"]["batch_size"] == 64
        assert meta["config"]["lr_decayed"] == 0.005
        assert meta["config"]["epoch"] == 1
        assert meta["summary"]["best_loss"] == 0.25
        assert meta["summary"]["best_accuracy"] == 0.95
        assert meta["summary"]["total_steps"] == num_steps
        assert meta["is_finished"] is True
        assert meta["exit_code"] == 0
        assert meta["finish_time"] is not None

        artifacts = meta["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "checkpoint.pt"
        assert artifacts[0]["description"] == "Best checkpoint"
        assert artifacts[0]["category"] == "model"

        # Artifact file
        artifact_path = base / run_name / "artifacts" / "checkpoint.pt"
        assert artifact_path.exists()
        assert artifact_path.read_bytes() == checkpoint_content

        # Project metadata
        project_meta = base / "metadata.json"
        assert project_meta.exists()
        with project_meta.open(encoding="utf-8") as f:
            proj_meta = json.load(f)
        assert set(proj_meta["tags"]) >= {"mnist", "classification"}
