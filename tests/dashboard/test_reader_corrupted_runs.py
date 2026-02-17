"""
Tests for RunCatalog's corrupted run detection functionality
"""

import tempfile
from pathlib import Path

from aspara.catalog import RunCatalog


class TestMetricsReaderCorruptedRuns:
    """Tests for RunCatalog's corrupted run detection functionality"""

    def test_empty_file_detection(self):
        """Test that empty run files are detected as corrupted"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directory structure
            logs_dir = Path(temp_dir)
            project_dir = logs_dir / "test_project"
            project_dir.mkdir(parents=True)

            # 空のRunファイルを作成
            empty_run_file = project_dir / "empty_run.jsonl"
            empty_run_file.touch()

            # Initialize RunCatalog and get runs
            run_catalog = RunCatalog(str(logs_dir))
            runs = run_catalog.get_runs("test_project")

            # Verify results
            assert len(runs) == 1
            run = runs[0]
            assert run.name == "empty_run"
            assert run.is_corrupted is True
            assert "Empty file" in run.error_message
            assert run.start_time is None
            # last_update uses file modification time, so it's set even for corrupted runs
            assert run.last_update is not None
            assert run.param_count == 0

    def test_invalid_json_detection(self):
        """Test that run files with invalid JSON are discovered but corruption is detected at load time.

        Note: For performance, get_runs() does lightweight corruption checks only.
        Invalid JSON is detected when load_metrics() is called.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directory structure
            logs_dir = Path(temp_dir)
            project_dir = logs_dir / "test_project"
            project_dir.mkdir(parents=True)

            # Create run file with invalid JSON
            invalid_json_file = project_dir / "invalid_json.jsonl"
            with open(invalid_json_file, "w") as f:
                f.write('{"type": "metrics", "timestamp": "2024-01-01T10:00:00"}\n')
                f.write('{"type": "metrics", timestamp: "2024-01-01T10:01:00"}\n')  # Invalid JSON

            # Initialize RunCatalog and get runs
            run_catalog = RunCatalog(str(logs_dir))
            runs = run_catalog.get_runs("test_project")

            # Verify run is discovered (lightweight check doesn't detect invalid JSON)
            assert len(runs) == 1
            run = runs[0]
            assert run.name == "invalid_json"
            # Corruption is detected at load time, not during get_runs()
            assert run.is_corrupted is False

    def test_missing_timestamp_detection(self):
        """Test that entries without timestamps are discovered but issue is detected at load time.

        Note: For performance, get_runs() does lightweight corruption checks only.
        Missing timestamps are detected when load_metrics() is called.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directory structure
            logs_dir = Path(temp_dir)
            project_dir = logs_dir / "test_project"
            project_dir.mkdir(parents=True)

            # Create run file without timestamp
            no_timestamp_file = project_dir / "no_timestamp.jsonl"
            with open(no_timestamp_file, "w") as f:
                f.write('{"metrics": {"loss": 0.5}}\n')  # No timestamp

            # Initialize RunCatalog and get runs
            run_catalog = RunCatalog(str(logs_dir))
            runs = run_catalog.get_runs("test_project")

            # Verify run is discovered (lightweight check doesn't validate timestamps)
            assert len(runs) == 1
            run = runs[0]
            assert run.name == "no_timestamp"
            # Corruption is detected at load time, not during get_runs()
            assert run.is_corrupted is False

    def test_valid_run_not_corrupted(self):
        """Test that valid run files are not detected as corrupted"""
        with tempfile.TemporaryDirectory() as temp_dir:
            import json

            # Create test directory structure
            logs_dir = Path(temp_dir)
            project_dir = logs_dir / "test_project"
            project_dir.mkdir(parents=True)

            # Create valid run file with metrics only
            valid_run_file = project_dir / "valid_run.jsonl"
            with open(valid_run_file, "w") as f:
                f.write('{"timestamp": "2024-01-01T10:00:00", "step": 0, "metrics": {"loss": 0.5}}\n')
                f.write('{"timestamp": "2024-01-01T10:01:00", "step": 1, "metrics": {"loss": 0.4}}\n')

            # Create metadata file
            meta_file = project_dir / "valid_run.meta.json"
            metadata = {
                "run_id": "test_id",
                "tags": [],
                "notes": "",
                "params": {"lr": 0.01},
                "config": {},
                "artifacts": [],
                "summary": {},
                "is_finished": False,
                "exit_code": None,
                "start_time": "2024-01-01T10:00:00",
                "finish_time": None,
            }
            with open(meta_file, "w") as f:
                json.dump(metadata, f)

            # Initialize RunCatalog and get runs
            run_catalog = RunCatalog(str(logs_dir))
            runs = run_catalog.get_runs("test_project")

            # Verify results
            assert len(runs) == 1
            run = runs[0]
            assert run.name == "valid_run"
            assert run.is_corrupted is False
            assert run.error_message is None
            assert run.start_time is not None
            assert run.last_update is not None
            assert run.param_count == 1  # 1 param key

    def test_multiple_runs_mixed(self):
        """Test case with mixed valid, empty, and invalid runs.

        Note: For performance, get_runs() only does lightweight corruption detection.
        Only empty files without metadata are detected as corrupted during get_runs().
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directory structure
            logs_dir = Path(temp_dir)
            project_dir = logs_dir / "test_project"
            project_dir.mkdir(parents=True)

            # Create valid run file
            valid_run_file = project_dir / "valid_run.jsonl"
            with open(valid_run_file, "w") as f:
                f.write('{"type": "metrics", "timestamp": "2024-01-01T10:00:00", "step": 0, "metrics": {"loss": 0.5}}\n')

            # Create empty run file
            empty_run_file = project_dir / "empty_run.jsonl"
            empty_run_file.touch()

            # Create run file with invalid JSON
            invalid_json_file = project_dir / "invalid_json.jsonl"
            with open(invalid_json_file, "w") as f:
                f.write('{"type": "metrics", "timestamp": "2024-01-01T10:00:00"}\n')
                f.write('{"type": "metrics", timestamp: "2024-01-01T10:01:00"}\n')  # Invalid JSON

            # Initialize RunCatalog and get runs
            run_catalog = RunCatalog(str(logs_dir))
            runs = run_catalog.get_runs("test_project")

            # Verify results
            assert len(runs) == 3

            # Sorted by name, so empty_run, invalid_json, valid_run in order
            assert runs[0].name == "empty_run"
            assert runs[0].is_corrupted is True  # Empty file detected as corrupted

            assert runs[1].name == "invalid_json"
            assert runs[1].is_corrupted is False  # Invalid JSON not detected until load_metrics()

            assert runs[2].name == "valid_run"
            assert runs[2].is_corrupted is False
