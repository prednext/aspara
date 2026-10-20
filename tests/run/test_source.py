"""Tests for automatic code-state capture."""

import subprocess
from pathlib import Path

from aspara.run._source import capture_code_state, sanitize_remote_url


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _dirty_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("x = 1\n")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-m", "init")
    (repo / "a.py").write_text("x = 2\n")


def test_sanitize_remote_strips_userinfo() -> None:
    assert sanitize_remote_url("https://user:ghp_token@github.com/org/repo.git") == "https://github.com/org/repo.git"


def test_sanitize_remote_leaves_scp_style() -> None:
    assert sanitize_remote_url("git@github.com:org/repo.git") == "git@github.com:org/repo.git"


def test_clean_git_records_sha(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "init")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()

    code = capture_code_state(cwd=tmp_path, dest_dir=tmp_path / "source")
    assert code["kind"] == "git"
    assert code["sha"] == head
    assert code["dirty"] is False
    assert not (tmp_path / "source" / "code.diff").exists()


def test_dirty_git_writes_diff(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "init")
    (tmp_path / "a.py").write_text("x = 2\n")

    dest = tmp_path / "out" / "source"
    code = capture_code_state(cwd=tmp_path, dest_dir=dest, base_dir=tmp_path)
    assert code["dirty"] is True
    assert code["snapshot_relpath"] == "source/code.diff"
    assert (dest / "code.diff").is_file()
    assert b"x = 2" in (dest / "code.diff").read_bytes()


def test_not_git_is_unavailable(tmp_path: Path) -> None:
    code = capture_code_state(cwd=tmp_path, dest_dir=tmp_path / "source")
    assert code["kind"] == "unavailable"


def test_run_dir_symlink_does_not_receive_diff(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _dirty_repo(repo)
    data_dir = tmp_path / "data"
    outside = tmp_path / "outside"
    outside.mkdir()
    (data_dir / "proj").mkdir(parents=True)
    (data_dir / "proj" / "run").symlink_to(outside, target_is_directory=True)

    code = capture_code_state(cwd=repo, dest_dir=data_dir / "proj" / "run" / "source", base_dir=data_dir)

    assert code["dirty"] is True
    assert code["sha"]
    assert code["snapshot_skipped"] == "unsafe_path"
    assert "snapshot_relpath" not in code
    assert not (outside / "source").exists()


def test_code_diff_symlink_is_not_overwritten(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _dirty_repo(repo)
    data_dir = tmp_path / "data"
    secret = data_dir / "secret.txt"
    secret.parent.mkdir()
    secret.write_bytes(b"keep-me")
    dest = data_dir / "proj" / "run" / "source"
    dest.mkdir(parents=True)
    (dest / "code.diff").symlink_to(secret)

    code = capture_code_state(cwd=repo, dest_dir=dest, base_dir=data_dir)

    assert code["snapshot_skipped"] == "unsafe_path"
    assert secret.read_bytes() == b"keep-me"
    assert (dest / "code.diff").is_symlink()


def test_init_does_not_write_diff_outside_data_dir(tmp_path: Path, monkeypatch) -> None:
    from aspara.run._api import finish, init

    repo = tmp_path / "repo"
    repo.mkdir()
    _dirty_repo(repo)
    monkeypatch.chdir(repo)
    data_dir = tmp_path / "data"
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_bytes(b"keep-me")
    (data_dir / "proj").mkdir(parents=True)
    (data_dir / "proj" / "run").symlink_to(outside, target_is_directory=True)
    source = data_dir / "proj" / "escaped" / "source"
    source.mkdir(parents=True)
    (source / "code.diff").symlink_to(secret)

    run = init(project="proj", name="run", dir=str(data_dir))
    try:
        assert not (outside / "source" / "code.diff").exists()
        code = run.backend._metadata_storage.get_metadata()["source"]["code"]
        assert code["snapshot_skipped"] == "unsafe_path"
        assert secret.read_bytes() == b"keep-me"
    finally:
        finish()

    escaped = init(project="proj", name="escaped", dir=str(data_dir))
    try:
        assert secret.read_bytes() == b"keep-me"
        assert (source / "code.diff").is_symlink()
        code = escaped.backend._metadata_storage.get_metadata()["source"]["code"]
        assert code["snapshot_skipped"] == "unsafe_path"
    finally:
        finish()
