"""Background sender for Tracker HTTP. Local writes never wait on this."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aspara.logger import logger
from aspara.run._offline_queue import MetricsQueueItem, MetricsRetryWorker, OfflineQueueStorage
from aspara.run._remote_run import TrackerClient

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _client_data_dir_for_tracker(tracker_uri: str, data_dir: str | None) -> str | None:
    """Absolute write path to send when the Tracker might be this machine."""
    host = (urlparse(tracker_uri).hostname or "").lower()
    if host not in _LOOPBACK_HOSTS or not data_dir:
        return None
    try:
        return str(Path(data_dir).expanduser().resolve())
    except OSError:
        return None


class TrackerShipper:
    """Queue create / metrics / finish / metadata to a Tracker.

    ``log()`` only enqueues. The retry worker performs HTTP.
    """

    def __init__(
        self,
        tracker_uri: str,
        *,
        project: str,
        run_name: str,
        run_id: str,
        name: str,
        config: dict[str, Any] | None,
        tags: list[str] | None,
        notes: str | None,
        project_tags: list[str] | None,
        resume: bool,
        intent: str,
        source: dict[str, Any],
        data_dir: str | None = None,
    ) -> None:
        self.client = TrackerClient(tracker_uri)
        self.project = project
        self.run_name = run_name
        self.run_id = run_id
        self._queue = OfflineQueueStorage(
            project=project,
            run_name=run_name,
            run_id=run_id,
            tracker_uri=tracker_uri,
            data_dir=Path(data_dir) if data_dir else None,
        )
        self._worker = MetricsRetryWorker(
            storage=self._queue,
            client=self.client,
            project=project,
            run_name=run_name,
        )
        create_payload = {
            "name": name,
            "project": project,
            "config": config,
            "tags": tags,
            "notes": notes,
            "project_tags": project_tags,
            "resume": resume,
            "intent": intent or None,
            "source": source or None,
            "run_id": run_id,
        }
        client_data_dir = _client_data_dir_for_tracker(tracker_uri, data_dir)
        if client_data_dir:
            create_payload["client_data_dir"] = client_data_dir
        try:
            response = self.client.create_run(**create_payload)
            if isinstance(response, dict) and response.get("same_store"):
                self._queue.reject_shipping(count_as_unsent=False)
                print("aspara: Tracker is storing this directory; not shipping a second copy")
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 409:
                self._queue.reject_shipping()
                print(f"aspara: Tracker already has '{run_name}' with a different id; not sending a copy")
                logger.warning(f"Tracker create returned 409 for {project}/{run_name}. Not retrying and not shipping further items.")
            else:
                logger.warning(f"Failed to create run on tracker: {exc}. Will retry via queue.")
                self._enqueue("create", payload=create_payload)
        self._worker.start()

    def _enqueue(
        self,
        kind: str,
        *,
        step: int = 0,
        metrics: dict[str, Any] | None = None,
        timestamp: int | str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._queue.enqueue(
            MetricsQueueItem(
                kind=kind,
                step=step,
                metrics=metrics or {},
                timestamp=timestamp,
                payload=payload or {},
            )
        )

    def offer_metrics(
        self,
        step: int,
        metrics: dict[str, Any],
        timestamp: int | str | None,
    ) -> None:
        self._enqueue("metrics", step=step, metrics=metrics, timestamp=timestamp)

    def offer_config(self, config: dict[str, Any]) -> None:
        self._enqueue("config", payload={"config": config})

    def offer_tags(self, tags: list[str]) -> None:
        self._enqueue("tags", payload={"tags": tags})

    def offer_summary(self, summary: dict[str, Any]) -> None:
        self._enqueue("summary", payload={"summary": summary})

    def offer_artifact(
        self,
        file_path: str,
        name: str | None,
        description: str | None,
        category: str | None,
    ) -> None:
        self._enqueue(
            "artifact",
            payload={
                "file_path": file_path,
                "name": name,
                "description": description,
                "category": category,
            },
        )

    def finish(self, exit_code: int, flush_timeout: float) -> None:
        self._enqueue("finish", payload={"exit_code": exit_code})
        self._worker.stop()
        self.flush(flush_timeout)
        self.client.close()

    def flush(self, timeout: float) -> int:
        return self._worker.flush_sync(timeout=timeout)
