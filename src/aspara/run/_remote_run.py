"""RemoteRun implementation for tracking metrics via HTTP to Aspara tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from aspara.logger import logger
from aspara.run._base_run import BaseRun
from aspara.run._config import Config
from aspara.run._offline_queue import MetricsQueueItem, MetricsRetryWorker, OfflineQueueStorage
from aspara.run._summary import Summary

if TYPE_CHECKING:
    import requests
else:
    try:
        import requests
    except ImportError:
        requests: Any = None  # Will raise error on RemoteRun instantiation

# Default timeout for HTTP requests in seconds
_DEFAULT_TIMEOUT = 30.0


class TrackerClient:
    """HTTP client for communicating with Aspara tracker."""

    def __init__(self, base_url: str) -> None:
        """Initialize tracker client.

        Args:
            base_url: Base URL of the tracker server (e.g., "http://localhost:3142")

        Raises:
            ImportError: If requests library is not installed
        """
        if requests is None:
            raise ImportError("requests library is required for RemoteRun. Install it with: pip install aspara[remote]")

        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        # Set X-Requested-With header for CSRF protection on all requests
        self.session.headers.update({"X-Requested-With": "XMLHttpRequest"})

    def create_run(
        self,
        name: str,
        project: str,
        config: dict[str, Any] | None,
        tags: list[str] | None,
        notes: str | None,
        project_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new run on the tracker.

        Args:
            name: Run name
            project: Project name
            config: Configuration parameters
            tags: List of tags
            notes: Run notes/description
            project_tags: Optional project-level tags

        Returns:
            Parsed JSON response from the tracker (expected to contain
            ``run_id`` and other metadata).

        Raises:
            requests.RequestException: If HTTP request fails.
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/projects/{quote(project, safe='')}/runs",
            json={
                "name": name,
                "config": config or {},
                "tags": tags or [],
                "notes": notes or "",
                "project_tags": project_tags,
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def save_metrics(
        self,
        project: str,
        run_name: str,
        step: int,
        metrics: dict[str, Any],
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Save metrics for a specific run.

        Args:
            project: Project name
            run_name: Run name
            step: Step number
            metrics: Dictionary of metric names to values
            timestamp: Optional timestamp in ISO format. If None, server will
                assign the timestamp.

        Raises:
            requests.RequestException: If HTTP request fails
        """

        payload: dict[str, Any] = {
            "step": step,
            "metrics": metrics,
        }
        if timestamp is not None:
            payload["timestamp"] = timestamp

        response = self.session.post(
            f"{self.base_url}/api/v1/projects/{quote(project, safe='')}/runs/{quote(run_name, safe='')}/metrics",
            json=payload,
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def log_config(self, project: str, run_name: str, config: dict[str, Any]) -> None:
        """Log config update to the tracker.

        Args:
            project: Project name
            run_name: Run name
            config: Configuration parameters

        Raises:
            requests.RequestException: If HTTP request fails
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/projects/{quote(project, safe='')}/runs/{quote(run_name, safe='')}/config",
            json={"config": config},
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

    def log_summary(self, project: str, run_name: str, summary: dict[str, Any]) -> None:
        """Log summary data to the tracker.

        Args:
            project: Project name
            run_name: Run name
            summary: Summary data

        Raises:
            requests.RequestException: If HTTP request fails
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/projects/{quote(project, safe='')}/runs/{quote(run_name, safe='')}/summary",
            json={"summary": summary},
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

    def finish_run(self, project: str, run_name: str, exit_code: int) -> None:
        """Finish the run on the tracker.

        Args:
            project: Project name
            run_name: Run name
            exit_code: Exit code (0 = success)

        Raises:
            requests.RequestException: If HTTP request fails
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/projects/{quote(project, safe='')}/runs/{quote(run_name, safe='')}/finish",
            json={"exit_code": exit_code},
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

    def health_check(self, timeout: float = 5.0) -> bool:
        """Check if the tracker server is healthy.

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if the server is healthy, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/health",
                timeout=timeout,
            )
            return response.status_code == 200
        except Exception:
            return False

    def log_artifact(
        self,
        project: str,
        run_name: str,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Upload an artifact file to the tracker.

        Args:
            project: Project name
            run_name: Run name
            file_path: Path to the file to upload
            name: Optional custom name for the artifact. If None, uses the filename.
            description: Optional description of the artifact
            category: Optional category ('code', 'model', 'config', 'data', 'other')

        Returns:
            Parsed JSON response from the tracker

        Raises:
            requests.RequestException: If HTTP request fails
        """
        import os

        # Prepare multipart form data
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {}
            if name:
                data["name"] = name
            if description:
                data["description"] = description
            if category:
                data["category"] = category

            response = self.session.post(
                f"{self.base_url}/api/v1/projects/{quote(project, safe='')}/runs/{quote(run_name, safe='')}/artifacts",
                files=files,
                data=data,
                timeout=_DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()


class RemoteRun(BaseRun):
    """A run that sends metrics to a remote Aspara tracker via HTTP."""

    def __init__(
        self,
        name: str | None = None,
        project: str | None = None,
        config: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        tracker_uri: str | None = None,
        project_tags: list[str] | None = None,
    ) -> None:
        """Initialize a new remote run.

        Args:
            name: Name of the run. If None, server will generate one.
            project: Project name this run belongs to. Defaults to "default".
            config: Initial configuration parameters.
            tags: List of tags for this run.
            notes: Run notes/description (wandb-compatible).
            tracker_uri: Tracker server URI (required for RemoteRun)

        Raises:
            ValueError: If tracker_uri is not provided
            ImportError: If requests library is not installed
        """
        if tracker_uri is None:
            raise ValueError("tracker_uri is required for RemoteRun")

        super().__init__(name=name, project=project, tags=tags, notes=notes)

        # Initialize tracker client
        self.client = TrackerClient(tracker_uri)

        # Create run on tracker
        try:
            response = self.client.create_run(
                name=self.name,
                project=self.project,
                config=config,
                tags=self.tags,
                notes=self.notes,
                project_tags=project_tags,
            )
            # Server always generates run_id
            self.id = response["run_id"]
            # Update name if server generated one
            if "name" in response:
                self.name = response["name"]
        except Exception as e:
            raise RuntimeError(f"Failed to create run on tracker: {e}") from e

        # Create config with sync callback
        def sync_config() -> None:
            try:
                self.client.log_config(self.project, self.name, self.config.to_dict())
            except Exception as e:
                logger.warning(f"Failed to sync config to tracker: {e}")

        self.config = Config(config, on_change=sync_config)

        # Create summary with sync callback
        def sync_summary() -> None:
            try:
                self.client.log_summary(self.project, self.name, self.summary.to_dict())
            except Exception as e:
                logger.warning(f"Failed to sync summary to tracker: {e}")

        self.summary = Summary(on_change=sync_summary)

        # Initialize offline queue for resilience
        self._tracker_uri = tracker_uri
        self._queue_storage = OfflineQueueStorage(
            project=self.project,
            run_name=self.name,
            run_id=self.id,
            tracker_uri=tracker_uri,
        )
        self._retry_worker = MetricsRetryWorker(
            storage=self._queue_storage,
            client=self.client,
            project=self.project,
            run_name=self.name,
        )
        self._retry_worker.start()

        logger.info(f"RemoteRun {self.name} initialized")
        logger.info(f"Sending metrics to: {tracker_uri}")

    def log(
        self,
        data: dict[str, Any],
        step: int | None = None,
        commit: bool = True,
        timestamp: str | None = None,
    ) -> None:
        """Log metrics and other data.

        Args:
            data: Dictionary of metric names to values
            step: Optional step number. If None, auto-increments.
            commit: If True, commits the step. If False, accumulates data.
            timestamp: Optional timestamp in ISO 8601 format. If provided, it is
                forwarded to the tracker; otherwise, the tracker assigns the
                timestamp on the server side.

        Raises:
            ValueError: If data contains invalid values
            RuntimeError: If run has already finished
        """
        self._ensure_not_finished()

        # Prepare step value (mirrors LocalRun behaviour)
        self._prepare_step(step, commit)

        # Validate and normalize metrics using shared helper
        metrics = self._validate_metrics(data)

        if metrics:
            try:
                self.client.save_metrics(
                    project=self.project,
                    run_name=self.name,
                    step=self._current_step,
                    metrics=metrics,
                    timestamp=timestamp,
                )
            except Exception as e:
                logger.warning(f"Failed to log metrics to tracker: {e}. Queueing for retry.")
                # Queue for later retry
                item = MetricsQueueItem(
                    step=self._current_step,
                    metrics=metrics,
                    timestamp=timestamp,
                )
                self._queue_storage.enqueue(item)

        self._after_log(commit)

    def finish(self, exit_code: int = 0, quiet: bool = False, flush_timeout: float = 30.0) -> None:
        """Finish the run and notify tracker.

        Args:
            exit_code: Exit code for the run (0 = success)
            quiet: If True, suppress output messages
            flush_timeout: Maximum time to wait for queue flush in seconds
        """
        if not self._mark_finished():
            return

        # Stop the background worker
        self._retry_worker.stop()

        # Flush any remaining queued metrics
        if not self._queue_storage.is_empty():
            self._retry_worker.flush_sync(timeout=flush_timeout)

        try:
            self.client.finish_run(self.project, self.name, exit_code)
        except Exception as e:
            logger.warning(f"Failed to finish run on tracker: {e}")

        if not quiet:
            logger.info(f"RemoteRun {self.name} finished with exit code {exit_code}")

    def log_artifact(
        self,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
    ) -> None:
        """Log an artifact file for this run.

        Args:
            file_path: Path to the file to be logged as an artifact
            name: Optional custom name for the artifact. If None, uses the filename.
            description: Optional description of the artifact
            category: Optional category ('code', 'model', 'config', 'data', 'other')

        Raises:
            ValueError: If file_path is invalid or file doesn't exist
            RuntimeError: If run has already finished
        """
        self._ensure_not_finished()

        # Validate input using shared helper
        abs_file_path, artifact_name = self._validate_artifact_input(file_path, name, category)

        # Upload artifact to tracker
        try:
            self.client.log_artifact(
                project=self.project,
                run_name=self.name,
                file_path=abs_file_path,
                name=artifact_name,
                description=description,
                category=category,
            )
        except Exception as e:
            logger.warning(f"Failed to upload artifact to tracker: {e}")

    def flush(self, timeout: float = 30.0) -> int:
        """Ensure all metrics are sent to tracker.

        Flushes any queued metrics that failed to send previously.

        Args:
            timeout: Maximum time to wait for flush in seconds

        Returns:
            Number of metrics that failed to send
        """
        if self._queue_storage.is_empty():
            return 0
        return self._retry_worker.flush_sync(timeout=timeout)

    def set_tags(self, tags: list[str]) -> None:
        """Set tags for this run.

        Note:
            This method is not yet supported for remote runs.

        Raises:
            NotImplementedError: Always raised as remote tag setting is not implemented.
        """
        raise NotImplementedError("set_tags is not yet supported for remote runs")
