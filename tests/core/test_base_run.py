from __future__ import annotations

import pytest

from aspara.run._base_run import BaseRun


class DummyRun(BaseRun):
    """Minimal concrete subclass for testing BaseRun behaviour."""

    def __init__(
        self,
        name: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> None:
        super().__init__(name=name, project=project, tags=tags, notes=notes)

    def log_step(self, step: int | None, commit: bool) -> int:
        """Helper to exercise step management API and return current step."""

        # Public wrappers in LocalRun/RemoteRun call these helpers in this order
        self._ensure_not_finished()
        prepared_step = self._prepare_step(step, commit)
        self._after_log(commit)
        # Return the step value used for logging (before auto-increment),
        # mirroring LocalRun/RemoteRun semantics.
        return prepared_step


class TestBaseRunState:
    def test_initial_state(self) -> None:
        run = DummyRun()

        assert run._current_step == 0
        assert run._step_committed is True
        assert run._finished is False

    def test_mark_finished_idempotent(self) -> None:
        run = DummyRun()

        # First call should transition to finished and return True
        assert run._mark_finished() is True
        assert run._finished is True

        # Subsequent calls should be no-op and return False
        assert run._mark_finished() is False
        assert run._finished is True


class TestBaseRunStepManagement:
    def test_auto_increment_step_with_commit(self) -> None:
        run = DummyRun()

        # First log without explicit step -> step 0 then increment to 1
        step0 = run.log_step(step=None, commit=True)
        assert step0 == 0
        assert run._current_step == 1

        # Second log -> step 1 then increment to 2
        step1 = run.log_step(step=None, commit=True)
        assert step1 == 1
        assert run._current_step == 2

    def test_explicit_step_overrides_current(self) -> None:
        run = DummyRun()

        # Move current step forward a bit
        run.log_step(step=None, commit=True)  # 0 -> 1

        # Explicit step should be used as-is
        step10 = run.log_step(step=10, commit=True)
        assert step10 == 10
        # After commit, internal counter is incremented
        assert run._current_step == 11

    def test_commit_false_does_not_increment_step(self) -> None:
        run = DummyRun()

        # Start at step 0, do not commit
        step0 = run.log_step(step=None, commit=False)
        assert step0 == 0
        assert run._current_step == 0
        assert run._step_committed is False

        # Next log with commit=True should still use step 0, then increment
        step_again = run.log_step(step=None, commit=True)
        assert step_again == 0
        assert run._current_step == 1


class TestBaseRunFinishedGuard:
    def test_ensure_not_finished_raises_after_mark_finished(self) -> None:
        run = DummyRun()

        # Initially should not raise
        run._ensure_not_finished()

        # After marking finished, guard should raise
        run._mark_finished()
        with pytest.raises(RuntimeError, match="Cannot log to a finished run"):
            run._ensure_not_finished()


class TestBaseRunMetricsValidation:
    def test_validate_metrics_accepts_numeric_values(self) -> None:
        run = DummyRun()

        metrics = run._validate_metrics({"loss": 0.5, "accuracy": 0.9, "count": 10})

        assert metrics == {"loss": 0.5, "accuracy": 0.9, "count": 10}

    def test_validate_metrics_rejects_empty_name(self) -> None:
        run = DummyRun()

        with pytest.raises(ValueError, match="Metric name cannot be empty"):
            run._validate_metrics({"": 1.0})

    def test_validate_metrics_rejects_unsupported_type(self) -> None:
        run = DummyRun()

        with pytest.raises(ValueError, match="Unsupported value type for 'loss'"):
            run._validate_metrics({"loss": "0.5"})
