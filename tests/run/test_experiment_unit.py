"""Experiment unit fields recorded on a local run."""

from pathlib import Path

from aspara.run._api import finish, init


def test_init_writes_intent_and_data(tmp_path: Path) -> None:
    run = init(
        project="p",
        name="r1",
        dir=str(tmp_path),
        intent="add lag features",
        data={"name": "sales", "uri": "s3://b/t", "version": "2026-01"},
    )
    try:
        meta = run.backend._metadata_storage.get_metadata()
        assert meta["intent"] == "add lag features"
        assert meta["source"]["data"][0]["uri"] == "s3://b/t"
        assert "kind" in meta["source"]["code"]
    finally:
        finish()


def test_resume_keeps_intent_and_data(tmp_path: Path) -> None:
    first = init(
        project="p",
        name="r3",
        dir=str(tmp_path),
        intent="add lag features",
        data={"uri": "s3://b/t", "version": "1"},
    )
    first.finish()
    resumed = init(project="p", name="r3", dir=str(tmp_path), resume=True)
    try:
        meta = resumed.backend._metadata_storage.get_metadata()
        assert meta["intent"] == "add lag features"
        assert meta["source"]["data"][0]["uri"] == "s3://b/t"
        assert "kind" in meta["source"]["code"]
    finally:
        finish()


def test_resume_keeps_source_code_when_git_fails(tmp_path: Path, monkeypatch) -> None:
    first = init(project="p", name="r-code", dir=str(tmp_path), intent="keep me")
    original = dict(first.backend._source["code"])
    first.finish()

    def boom(*_args, **_kwargs):
        raise RuntimeError("git down")

    monkeypatch.setattr("aspara.run._source.capture_code_state", boom)
    resumed = init(project="p", name="r-code", dir=str(tmp_path), resume=True)
    try:
        meta = resumed.backend._metadata_storage.get_metadata()
        assert meta["source"]["code"] == original
        assert meta["intent"] == "keep me"
    finally:
        finish()
