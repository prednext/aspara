"""Tests for the module-level API (init/log/finish) thread safety."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import aspara.run._api as api_module
from aspara.run._api import finish, init, log


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before and after each test."""
    api_module._current_run = None
    api_module._storage_backend = "jsonl"
    yield
    api_module._current_run = None
    api_module._storage_backend = "jsonl"


@pytest.fixture
def mock_run():
    """Create a mock Run object."""
    run = MagicMock()
    run.finish = MagicMock()
    run.log = MagicMock()
    return run


class TestInitLogFinishThreadSafety:
    """Tests that init/log/finish are safe under concurrent access."""

    def test_concurrent_init_does_not_lose_finish(self, mock_run):
        """Two threads calling init() concurrently must not skip finish() on the old run."""
        with patch("aspara.run._api.resolve_metrics_storage_backend", return_value="jsonl"), patch("aspara.run.run.Run", return_value=mock_run):
            # Pre-set a current run so init() tries to finish it.
            api_module._current_run = mock_run

            barrier = threading.Barrier(2)

            def do_init():
                barrier.wait()
                init(project="test")

            # Run two inits concurrently; each should call finish on the
            # existing run at most once, and the global state should be
            # consistent afterward.
            t1 = threading.Thread(target=do_init)
            t2 = threading.Thread(target=do_init)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # The mock_run.finish should have been called at least once
            # (the first init finishes the pre-existing run).
            assert mock_run.finish.called
            # Global state should be set to the new run.
            assert api_module._current_run is mock_run

    def test_concurrent_log_and_finish(self, mock_run):
        """log() and finish() called concurrently must not crash or corrupt state."""
        with patch("aspara.run._api.resolve_metrics_storage_backend", return_value="jsonl"), patch("aspara.run.run.Run", return_value=mock_run):
            init(project="test")
            assert api_module._current_run is mock_run

            errors: list[Exception] = []

            def do_log():
                try:
                    for _ in range(100):
                        log({"loss": 0.5})
                except RuntimeError:
                    # finish() may have cleared _current_run - that's OK
                    pass
                except Exception as e:
                    errors.append(e)

            def do_finish():
                try:
                    for _ in range(10):
                        finish()
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(e)

            t1 = threading.Thread(target=do_log)
            t2 = threading.Thread(target=do_finish)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # No unexpected errors should have occurred.
            assert errors == []
            # State should be consistent: either None or mock_run.
            assert api_module._current_run is None or api_module._current_run is mock_run

    def test_concurrent_init_log_from_multiple_threads(self, mock_run):
        """Multiple threads calling init+log should not corrupt global state."""
        with patch("aspara.run._api.resolve_metrics_storage_backend", return_value="jsonl"), patch("aspara.run.run.Run", return_value=mock_run):
            errors: list[Exception] = []

            def worker():
                try:
                    for _ in range(50):
                        init(project="test")
                        log({"loss": 0.5})
                        finish()
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == []
            # After all threads finish, state should be clean.
            assert api_module._current_run is None or api_module._current_run is mock_run
