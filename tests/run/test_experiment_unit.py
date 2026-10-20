"""Experiment unit fields and local-first tracker shipping."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

from aspara.run._api import finish, init
from aspara.run._local_run import LocalRun
from aspara.run._offline_queue import MetricsQueueItem


def test_resume_keeps_code_state(tmp_path: Path) -> None:
    first = init(
        project="p",
        name="r3",
        dir=str(tmp_path),
        notes="add lag features",
    )
    first.finish()
    resumed = init(project="p", name="r3", dir=str(tmp_path), resume=True)
    try:
        meta = resumed.backend._metadata_storage.get_metadata()
        assert "kind" in meta["source"]["code"]
    finally:
        finish()


def test_tracker_uri_still_writes_local_files(tmp_path: Path, monkeypatch) -> None:
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"run_id": "server", "name": "r2"}
    mock_session.post.return_value = mock_response

    def mock_init(self, base_url):
        self.base_url = base_url
        self.session = mock_session

    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.__init__", mock_init)
    monkeypatch.setattr(
        "aspara.run._tracker_client.TrackerClient.create_run",
        lambda self, **kwargs: {"run_id": "server", "name": kwargs["name"]},
    )
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", lambda self, **kwargs: {"status": "ok"})
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.finish_run", lambda self, *a, **k: None)

    run = init(
        project="p",
        name="r2",
        dir=str(tmp_path),
        tracker_uri="http://localhost:3142",
    )
    try:
        assert isinstance(run.backend, LocalRun)
        assert (tmp_path / "p" / "r2.meta.json").is_file()
        run.log({"loss": 0.1})
        assert (tmp_path / "p" / "r2.jsonl").is_file()
    finally:
        finish()


def _mock_tracker(monkeypatch, *, create_run=None) -> None:
    from unittest.mock import MagicMock

    def mock_init(self, base_url):
        self.base_url = base_url
        self.session = MagicMock()

    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.__init__", mock_init)
    monkeypatch.setattr(
        "aspara.run._tracker_client.TrackerClient.create_run",
        create_run or (lambda self, **kwargs: {"run_id": "server", "name": kwargs["name"]}),
    )
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", lambda self, **kwargs: {"status": "ok"})
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.finish_run", lambda self, *a, **k: None)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.log_config", lambda self, *a, **k: None)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.log_summary", lambda self, *a, **k: None)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.update_tags", lambda self, *a, **k: None)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.log_artifact", lambda self, **k: {"status": "ok"})
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.health_check", lambda self, timeout=5.0: True)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.close", lambda self: None)


def test_same_data_dir_does_not_ship(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path))
    saved = MagicMock(return_value={"status": "ok"})
    created = MagicMock(return_value={"run_id": "local", "same_store": True, "name": "same-dir"})
    _mock_tracker(monkeypatch, create_run=created)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", saved)
    run = init(project="p", name="same-dir", tracker_uri="http://127.0.0.1:3142")
    try:
        assert run.backend._shipper is not None
        created.assert_called()
        assert created.call_args.kwargs["client_data_dir"] == str(tmp_path.resolve())
        run.log({"loss": 0.1})
        saved.assert_not_called()
        assert (tmp_path / "p" / "same-dir.jsonl").is_file()
    finally:
        finish()


def test_other_data_dir_does_ship(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASPARA_DATA_DIR", str(tmp_path / "tracker-store"))
    created = MagicMock(return_value={"run_id": "server", "name": "other-dir"})
    _mock_tracker(monkeypatch, create_run=created)
    run = init(
        project="p",
        name="other-dir",
        dir=str(tmp_path / "client"),
        tracker_uri="http://localhost:3142",
    )
    try:
        assert run.backend._shipper is not None
        created.assert_called()
        assert created.call_args.kwargs["client_data_dir"] == str((tmp_path / "client").resolve())
    finally:
        finish()


def test_resume_keeps_source_code_when_git_fails(tmp_path: Path, monkeypatch) -> None:
    first = init(project="p", name="r-code", dir=str(tmp_path), notes="keep me")
    original = dict(first.backend._source["code"])
    first.finish()

    def boom(*_args, **_kwargs):
        raise RuntimeError("git down")

    monkeypatch.setattr("aspara.run._source.capture_code_state", boom)
    resumed = init(project="p", name="r-code", dir=str(tmp_path), resume=True)
    try:
        meta = resumed.backend._metadata_storage.get_metadata()
        assert meta["source"]["code"] == original
    finally:
        finish()


def test_create_failure_is_retried_on_flush(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}

    def create_run(self, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("tracker down")
        return {"run_id": "server", "name": kwargs["name"]}

    _mock_tracker(monkeypatch, create_run=create_run)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.health_check", lambda self, timeout=5.0: False)
    run = init(
        project="p",
        name="retry-create",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
    )
    try:
        assert calls["n"] == 1
        assert run.backend._shipper is not None
        run.log({"loss": 0.2})
        failed = run.flush(timeout=5.0)
        assert failed == 0
        assert calls["n"] >= 2
    finally:
        finish()


def test_log_does_not_call_save_metrics_inline(tmp_path: Path, monkeypatch) -> None:
    saved = MagicMock(return_value={"status": "ok"})
    _mock_tracker(monkeypatch)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", saved)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.health_check", lambda self, timeout=5.0: False)
    run = init(
        project="p",
        name="async-log",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
    )
    try:
        run.log({"loss": 0.3})
        saved.assert_not_called()
        run.flush(timeout=5.0)
        saved.assert_called()
    finally:
        finish()


def test_shipped_timestamp_matches_the_local_file(tmp_path: Path, monkeypatch) -> None:
    saved = MagicMock(return_value={"status": "ok"})
    _mock_tracker(monkeypatch)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", saved)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.health_check", lambda self, timeout=5.0: False)
    run = init(
        project="p",
        name="same-time",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
    )
    try:
        run.log({"loss": 0.1})
        run.log({"loss": 0.2}, timestamp="2024-06-15T10:30:00")
        lines = [json.loads(line) for line in (tmp_path / "p" / "same-time.jsonl").read_text().splitlines()]
        run.flush(timeout=5.0)
        sent = [call.kwargs["timestamp"] for call in saved.call_args_list]
        assert sent == [line["timestamp"] for line in lines]
        assert lines[1]["timestamp"] == 1718447400000
        assert all(isinstance(value, int) for value in sent)
    finally:
        finish()


def test_config_and_tags_are_queued_for_tracker(tmp_path: Path, monkeypatch) -> None:
    logged_config = MagicMock()
    updated_tags = MagicMock()
    _mock_tracker(monkeypatch)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.log_config", logged_config)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.update_tags", updated_tags)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.health_check", lambda self, timeout=5.0: False)
    run = init(
        project="p",
        name="meta-ship",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
        config={"lr": 0.01},
    )
    try:
        run.config["lr"] = 0.02
        run.set_tags(["baseline"])
        logged_config.assert_not_called()
        updated_tags.assert_not_called()
        run.flush(timeout=5.0)
        logged_config.assert_called()
        updated_tags.assert_called()
    finally:
        finish()


def test_finish_stops_worker_before_flush(tmp_path: Path, monkeypatch) -> None:
    order: list[str] = []
    _mock_tracker(monkeypatch)
    run = init(
        project="p",
        name="finish-order",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
    )
    shipper = run.backend._shipper
    assert shipper is not None
    original_stop = shipper._worker.stop
    original_flush = shipper._worker.flush_sync

    def stop(timeout: float = 5.0) -> None:
        order.append("stop")
        original_stop(timeout)

    def flush_sync(timeout: float = 30.0) -> int:
        order.append("flush")
        return original_flush(timeout)

    shipper._worker.stop = stop  # type: ignore[method-assign]
    shipper._worker.flush_sync = flush_sync  # type: ignore[method-assign]
    finish()
    assert order[:2] == ["stop", "flush"]


def test_shipper_sends_local_run_id(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}

    def create_run(self, **kwargs):
        captured.update(kwargs)
        return {"run_id": "server-other-id", "name": kwargs["name"]}

    _mock_tracker(monkeypatch, create_run=create_run)
    run = init(
        project="p",
        name="same-id",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
    )
    try:
        assert captured["run_id"] == run.id
        assert "client_data_dir" not in captured
        assert run.backend._shipper is not None
        assert run.backend._shipper.run_id == run.id
        meta_path = tmp_path / "p" / "same-id.meta.json"
        assert json.loads(meta_path.read_text())["run_id"] == run.id
    finally:
        finish()


def test_create_conflict_does_not_ship_or_retry(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}
    saved = MagicMock(return_value={"status": "ok"})

    def create_run(self, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("tracker down")
        conflict = Exception("conflict")
        conflict.response = MagicMock(status_code=409)
        raise conflict

    _mock_tracker(monkeypatch, create_run=create_run)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", saved)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.health_check", lambda self, timeout=5.0: False)
    run = init(
        project="p",
        name="conflict",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
    )
    try:
        run.log({"loss": 0.4})
        failed = run.flush(timeout=5.0)
        assert calls["n"] == 2
        assert failed == 2
        saved.assert_not_called()
        assert run.backend._shipper is not None
        assert run.backend._shipper.run_id == run.id
    finally:
        finish()


def test_resume_drops_a_queued_finish(tmp_path: Path, monkeypatch) -> None:
    first = init(project="p", name="held", dir=str(tmp_path))
    first.finish()
    queue_dir = tmp_path / ".queue" / "p"
    queue_dir.mkdir(parents=True)
    queued = MetricsQueueItem(step=7, metrics={"loss": 0.2})
    leftover = MetricsQueueItem(kind="finish", payload={"exit_code": 1})
    (queue_dir / "held.queue.jsonl").write_text(queued.to_jsonl() + "\n" + leftover.to_jsonl() + "\n")

    finished: list[int] = []
    saved: list[int] = []

    def finish_run(self, project, run_name, exit_code):
        finished.append(exit_code)

    def save_metrics(self, **kwargs):
        saved.append(kwargs["step"])
        return {"status": "ok"}

    _mock_tracker(monkeypatch)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.finish_run", finish_run)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", save_metrics)
    resumed = init(
        project="p",
        name="held",
        dir=str(tmp_path),
        resume=True,
        tracker_uri="http://tracker.example:3142",
    )
    try:
        deadline = time.time() + 2
        while not saved and time.time() < deadline:
            time.sleep(0.01)
        assert saved == [7]
        assert finished == []
        assert resumed.backend._shipper is not None
    finally:
        finish()


def test_sync_create_conflict_does_not_ship_metrics(tmp_path: Path, monkeypatch, capsys) -> None:
    calls = {"n": 0}
    saved = MagicMock(return_value={"status": "ok"})

    def create_run(self, **kwargs):
        calls["n"] += 1
        conflict = Exception("conflict")
        conflict.response = MagicMock(status_code=409)
        raise conflict

    _mock_tracker(monkeypatch, create_run=create_run)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", saved)
    run = init(
        project="p",
        name="sync-conflict",
        dir=str(tmp_path),
        tracker_uri="http://tracker.example:3142",
    )
    try:
        assert "not sending a copy" in capsys.readouterr().out
        run.log({"loss": 0.5})
        failed = run.flush(timeout=2.0)
        assert calls["n"] == 1
        assert failed == 1
        saved.assert_not_called()
        meta = json.loads((tmp_path / "p" / "sync-conflict.meta.json").read_text())
        assert meta["run_id"] == run.id
    finally:
        finish()


def test_queued_same_store_does_not_ship_metrics(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}
    saved = MagicMock(return_value={"status": "ok"})

    def create_run(self, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("tracker down")
        return {"run_id": kwargs.get("run_id"), "same_store": True, "name": kwargs["name"]}

    _mock_tracker(monkeypatch, create_run=create_run)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.save_metrics", saved)
    monkeypatch.setattr("aspara.run._tracker_client.TrackerClient.health_check", lambda self, timeout=5.0: False)
    run = init(
        project="p",
        name="same-later",
        dir=str(tmp_path),
        tracker_uri="http://127.0.0.1:3142",
    )
    try:
        run.log({"loss": 0.4})
        failed = run.flush(timeout=5.0)
        assert calls["n"] == 2
        assert failed == 0
        saved.assert_not_called()
    finally:
        finish()
