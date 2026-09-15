"""Filesystem artifact store: delete removes bytes without leaving the tenant root."""

from __future__ import annotations

from pathlib import Path

import pytest

from aspara.storage.artifacts import FilesystemArtifactStore


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
