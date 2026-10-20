"""HTTP client for sending a run copy to an Aspara Tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from aspara.logger import logger

if TYPE_CHECKING:
    import requests
else:
    try:
        import requests
    except ImportError:
        requests: Any = None  # Will raise error on TrackerClient instantiation

# Default timeout for HTTP requests in seconds
_DEFAULT_TIMEOUT = 30.0


class TrackerClient:
    """HTTP client for communicating with Aspara tracker."""

    def __init__(self, base_url: str) -> None:
        """Initialize tracker client.

        Args:
            base_url: Base URL of the tracker server (e.g., "http://localhost:3142/tracker")

        Raises:
            ImportError: If requests library is not installed
        """
        if requests is None:
            raise ImportError('requests library is required to reach a Tracker. Install it with: pip install "aspara[remote]"')

        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        # Set X-Requested-With header for CSRF protection on all requests
        self.session.headers.update({"X-Requested-With": "XMLHttpRequest"})

    def close(self) -> None:
        """Close the HTTP session and release connection pool resources."""
        self.session.close()

    def __enter__(self) -> TrackerClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def create_run(
        self,
        name: str,
        project: str,
        config: dict[str, Any] | None,
        tags: list[str] | None,
        notes: str | None,
        project_tags: list[str] | None = None,
        resume: bool = False,
        source: dict[str, Any] | None = None,
        run_id: str | None = None,
        client_data_dir: str | None = None,
    ) -> dict[str, Any]:
        """Create a new run on the tracker.

        Args:
            name: Run name
            project: Project name
            config: Configuration parameters
            tags: List of tags
            notes: Run notes/description
            project_tags: Optional project-level tags
            resume: If True, resume an existing run with the same name
            run_id: Client run id. The tracker stores this on create.
            client_data_dir: Absolute directory the client is writing. Sent
                for loopback trackers so the server can refuse a second copy.

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
                "resume": resume,
                **({"source": source} if source else {}),
                **({"run_id": run_id} if run_id else {}),
                **({"client_data_dir": client_data_dir} if client_data_dir else {}),
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
        timestamp: int | str | None = None,
    ) -> dict[str, Any]:
        """Save metrics for a specific run.

        Args:
            project: Project name
            run_name: Run name
            step: Step number
            metrics: Dictionary of metric names to values
            timestamp: UNIX milliseconds, or an ISO string. If None, the
                server assigns the time. Local runs pass the milliseconds
                already written to disk.

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

    def update_tags(self, project: str, run_name: str, tags: list[str]) -> None:
        """Update tags for a run on the tracker.

        Args:
            project: Project name
            run_name: Run name
            tags: New list of tags (replaces existing tags)

        Raises:
            requests.RequestException: If HTTP request fails
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/projects/{quote(project, safe='')}/runs/{quote(run_name, safe='')}/tags",
            json={"tags": tags},
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
        except requests.RequestException as e:
            logger.debug(f"Health check failed: {e}")
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
