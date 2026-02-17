"""
Tests for the artifacts ZIP download functionality.
"""

import io
import os
import tempfile
import zipfile

from fastapi.testclient import TestClient

from aspara.dashboard.main import app


class TestArtifactZipDownload:
    """Test suite for artifacts ZIP download functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for test artifacts
        self.temp_dir = tempfile.mkdtemp()
        self.test_project = "test_project"
        self.test_run = "test_run"

        # Create artifacts directory structure
        self.artifacts_dir = os.path.join(self.temp_dir, self.test_project, self.test_run, "artifacts")
        os.makedirs(self.artifacts_dir, exist_ok=True)

        # Create test artifact files
        self.test_files = {
            "config.json": '{"learning_rate": 0.01, "batch_size": 32}',
            "model.py": "import torch\nclass Model(torch.nn.Module):\n    pass",
            "training.log": "Epoch 1: loss=0.5\nEpoch 2: loss=0.3\nTraining completed",
            "weights.pt": "binary_model_data_placeholder",
        }

        for filename, content in self.test_files.items():
            with open(os.path.join(self.artifacts_dir, filename), "w") as f:
                f.write(content)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_download_artifacts_success(self):
        """Test successful artifact ZIP download."""
        # Initialize services with temp directory
        from aspara.dashboard.router import configure_data_dir

        configure_data_dir(self.temp_dir)

        client = TestClient(app)
        response = client.get(f"/api/projects/{self.test_project}/runs/{self.test_run}/artifacts/download")

        # Check response status and headers
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers["content-disposition"]
        assert f"{self.test_project}_{self.test_run}_artifacts_" in response.headers["content-disposition"]
        assert ".zip" in response.headers["content-disposition"]

    def test_download_artifacts_zip_content(self):
        """Test that ZIP contains correct files with correct content."""
        # Initialize services with temp directory
        from aspara.dashboard.router import configure_data_dir

        configure_data_dir(self.temp_dir)

        client = TestClient(app)
        response = client.get(f"/api/projects/{self.test_project}/runs/{self.test_run}/artifacts/download")

        assert response.status_code == 200

        # Parse ZIP content
        zip_content = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_content, "r") as zip_file:
            # Check that all expected files are in the ZIP
            zip_files = zip_file.namelist()
            assert len(zip_files) == len(self.test_files)

            for expected_file in self.test_files:
                assert expected_file in zip_files

            # Check file contents
            for filename, expected_content in self.test_files.items():
                with zip_file.open(filename) as f:
                    actual_content = f.read().decode("utf-8")
                    assert actual_content == expected_content

    def test_download_artifacts_no_directory(self):
        """Test error when artifacts directory doesn't exist."""
        # Initialize services with non-existent path
        from aspara.dashboard.router import configure_data_dir

        configure_data_dir("/non/existent/path")

        client = TestClient(app)
        response = client.get(f"/api/projects/{self.test_project}/runs/{self.test_run}/artifacts/download")

        assert response.status_code == 404
        assert response.json()["detail"] == "No artifacts found for this run"

    def test_download_artifacts_empty_directory(self):
        """Test error when artifacts directory exists but is empty."""
        import os

        # Initialize services with temp directory
        from aspara.dashboard.router import configure_data_dir

        configure_data_dir(self.temp_dir)

        # Create empty artifacts directory
        empty_run = "empty_run"
        empty_artifacts_dir = os.path.join(self.temp_dir, self.test_project, empty_run, "artifacts")
        os.makedirs(empty_artifacts_dir, exist_ok=True)

        client = TestClient(app)
        response = client.get(f"/api/projects/{self.test_project}/runs/{empty_run}/artifacts/download")

        assert response.status_code == 404
        assert response.json()["detail"] == "No artifact files found"

    def test_download_artifacts_directory_with_subdirs(self):
        """Test that only files are included, not subdirectories."""
        import os

        # Initialize services with temp directory
        from aspara.dashboard.router import configure_data_dir

        configure_data_dir(self.temp_dir)

        # Create a subdirectory in artifacts (should be ignored)
        subdir = os.path.join(self.artifacts_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        with open(os.path.join(subdir, "nested_file.txt"), "w") as f:
            f.write("This should not be included")

        client = TestClient(app)
        response = client.get(f"/api/projects/{self.test_project}/runs/{self.test_run}/artifacts/download")

        assert response.status_code == 200

        # Parse ZIP content and ensure subdirectories are not included
        zip_content = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_content, "r") as zip_file:
            zip_files = zip_file.namelist()

            # Should only contain the original files, not the subdirectory
            assert len(zip_files) == len(self.test_files)
            for expected_file in self.test_files:
                assert expected_file in zip_files

            # Ensure subdirectory and its contents are not included
            assert "subdir" not in zip_files
            assert "subdir/nested_file.txt" not in zip_files
            assert "nested_file.txt" not in zip_files

    def test_download_artifacts_large_files(self):
        """Test ZIP download with larger files."""
        import os

        # Initialize services with temp directory
        from aspara.dashboard.router import configure_data_dir

        configure_data_dir(self.temp_dir)

        # Create a larger test file
        large_content = "x" * 10000  # 10KB of data
        large_file_path = os.path.join(self.artifacts_dir, "large_file.txt")
        with open(large_file_path, "w") as f:
            f.write(large_content)

        client = TestClient(app)
        response = client.get(f"/api/projects/{self.test_project}/runs/{self.test_run}/artifacts/download")

        assert response.status_code == 200
        assert len(response.content) > 500  # Should be reasonably large (compressed)

        # Verify the large file is included with correct content
        zip_content = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_content, "r") as zip_file:
            assert "large_file.txt" in zip_file.namelist()
            with zip_file.open("large_file.txt") as f:
                actual_content = f.read().decode("utf-8")
                assert actual_content == large_content

    def test_download_artifacts_special_characters_in_filename(self):
        """Test ZIP download with files containing special characters."""
        import os

        # Initialize services with temp directory
        from aspara.dashboard.router import configure_data_dir

        configure_data_dir(self.temp_dir)

        # Create files with special characters in names
        special_files = {
            "file with spaces.txt": "content1",
            "file-with-dashes.json": "content2",
            "file_with_underscores.py": "content3",
        }

        for filename, content in special_files.items():
            with open(os.path.join(self.artifacts_dir, filename), "w") as f:
                f.write(content)

        client = TestClient(app)
        response = client.get(f"/api/projects/{self.test_project}/runs/{self.test_run}/artifacts/download")

        assert response.status_code == 200

        # Verify all files are included
        zip_content = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_content, "r") as zip_file:
            zip_files = zip_file.namelist()

            # Should include both original files and special character files
            for expected_file in list(self.test_files.keys()) + list(special_files.keys()):
                assert expected_file in zip_files

    def test_download_artifacts_invalid_parameters(self):
        """Test error handling with invalid project/run parameters."""
        client = TestClient(app)

        # Test with path traversal - may get normalized by framework to 404
        response = client.get("/api/projects/../../../etc/runs/hack/artifacts/download")
        assert response.status_code in [400, 404]  # Either validation rejects or routing fails

        # Test with spaces - should definitely be rejected by validation
        response = client.get("/api/projects/project%20with%20spaces/runs/run/artifacts/download")
        assert response.status_code == 400

        # Empty strings result in 404 because the route doesn't match
        response = client.get("/api/projects//runs//artifacts/download")
        assert response.status_code == 404


class TestArtifactZipDownloadIntegration:
    """Integration tests for ZIP download with real Run artifacts."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up integration test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_download_artifacts_after_run_creation(self):
        """Integration test: create run with artifacts, then download."""
        from aspara.run import Run

        # Create a run and log some artifacts using the temp directory
        run = Run("integration_test_run", project="test_proj", dir=self.temp_dir)

        # Create test files to upload as artifacts
        test_files = []
        for i, (name, content) in enumerate([
            ("config.yaml", "setting: value"),
            ("script.py", "print('hello')"),
        ]):
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=f"_{name}") as temp_file:
                temp_file.write(content)
                temp_file.close()
                test_files.append((temp_file.name, name, content))

                # Log as artifact
                run.log_artifact(temp_file.name, name=name, description=f"Test artifact {i + 1}", category="config" if name.endswith(".yaml") else "code")
        try:
            # Initialize services with temp directory
            from aspara.dashboard.router import configure_data_dir

            configure_data_dir(self.temp_dir)

            # Now test downloading the artifacts
            client = TestClient(app)
            response = client.get("/api/projects/test_proj/runs/integration_test_run/artifacts/download")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/zip"

            # Verify ZIP contents
            zip_content = io.BytesIO(response.content)
            with zipfile.ZipFile(zip_content, "r") as zip_file:
                zip_files = zip_file.namelist()
                assert "config.yaml" in zip_files
                assert "script.py" in zip_files

                # Verify content
                with zip_file.open("config.yaml") as f:
                    assert f.read().decode("utf-8") == "setting: value"
                with zip_file.open("script.py") as f:
                    assert f.read().decode("utf-8") == "print('hello')"

        finally:
            # Clean up temporary files
            for temp_file_path, _, _ in test_files:
                os.unlink(temp_file_path)
