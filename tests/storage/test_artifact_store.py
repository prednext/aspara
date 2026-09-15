"""Filesystem artifact store: delete removes bytes without leaving the tenant root."""

from __future__ import annotations

from pathlib import Path

import pytest

from aspara.storage.artifacts import ArtifactTooLargeError, FilesystemArtifactStore


def test_delete_run_removes_run_dir_and_leaves_sibling(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    gone = tmp_path / "proj" / "gone" / "artifacts"
    keep = tmp_path / "proj" / "keep" / "artifacts"
    gone.mkdir(parents=True)
    keep.mkdir(parents=True)
    (gone / "old.pt").write_bytes(b"stale")
    (keep / "ok.pt").write_bytes(b"keep")

    store.delete_run("proj", "gone")

    assert not (tmp_path / "proj" / "gone").exists()
    assert (keep / "ok.pt").read_bytes() == b"keep"


def test_delete_run_missing_is_noop(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    store.delete_run("proj", "missing")


def test_delete_project_removes_project_dir_not_store_root(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    (tmp_path / "aspara.db").write_bytes(b"db")
    artifacts = tmp_path / "proj" / "r1" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "model.pt").write_bytes(b"weights")
    other = tmp_path / "other" / "r1" / "artifacts"
    other.mkdir(parents=True)
    (other / "x.pt").write_bytes(b"other")

    store.delete_project("proj")

    assert not (tmp_path / "proj").exists()
    assert (tmp_path / "aspara.db").read_bytes() == b"db"
    assert (other / "x.pt").read_bytes() == b"other"


def test_delete_rejects_unsafe_names(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    with pytest.raises(ValueError):
        store.delete_run("..", "r1")
    with pytest.raises(ValueError):
        store.delete_run("proj", "../etc")
    with pytest.raises(ValueError):
        store.delete_project("..")


def test_delete_file_removes_one_artifact(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    artifacts = tmp_path / "proj" / "r1" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "a.pt").write_bytes(b"a")
    (artifacts / "b.pt").write_bytes(b"b")
    store.delete_file("proj", "r1", "a.pt")
    assert not (artifacts / "a.pt").exists()
    assert (artifacts / "b.pt").read_bytes() == b"b"


def test_put_stream_publishes_via_replace_and_cleans_partial(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    stored = store.put_stream("proj", "r1", "model.pt", [b"abc", b"def"], max_size=100)
    dest = tmp_path / "proj" / "r1" / "artifacts" / "model.pt"
    assert stored.size == 6
    assert dest.read_bytes() == b"abcdef"
    assert not dest.with_name("model.pt.partial").exists()


def test_put_stream_oversize_leaves_no_partial_or_dest(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    with pytest.raises(ArtifactTooLargeError):
        store.put_stream("proj", "r1", "model.pt", [b"abcdef"], max_size=3)
    artifacts = tmp_path / "proj" / "r1" / "artifacts"
    assert not (artifacts / "model.pt").exists()
    assert not (artifacts / "model.pt.partial").exists()


def test_abort_put_after_stage_leaves_existing_dest(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    store.put_stream("proj", "r1", "model.pt", [b"old"], max_size=100)
    dest = tmp_path / "proj" / "r1" / "artifacts" / "model.pt"
    store.stage_stream("proj", "r1", "model.pt", [b"newbytes"], max_size=100)
    assert dest.read_bytes() == b"old"
    store.abort_put("proj", "r1", "model.pt")
    assert dest.read_bytes() == b"old"
    assert not dest.with_name("model.pt.partial").exists()


def test_list_skips_partial_temp_files(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    artifacts = tmp_path / "proj" / "r1" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "ok.pt").write_bytes(b"ok")
    (artifacts / "ok.pt.partial").write_bytes(b"tmp")
    names = {entry.name for entry in store.list("proj", "r1")}
    assert names == {"ok.pt"}
