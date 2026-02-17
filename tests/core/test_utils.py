from types import SimpleNamespace

from aspara import utils
from aspara.utils import file as utils_file


def test_utils_package_exports_all_functions():
    """Ensure all utility functions are importable from aspara.utils."""
    from aspara.utils import atomic_write_json, datasync, parse_to_datetime, parse_to_ms

    assert callable(atomic_write_json)
    assert callable(datasync)
    assert callable(parse_to_datetime)
    assert callable(parse_to_ms)


def test_atomic_write_json_creates_file(tmp_path):
    """Test that atomic_write_json creates a JSON file correctly."""
    test_file = tmp_path / "test.json"
    data = {"key": "value", "number": 42}

    utils.atomic_write_json(test_file, data)

    assert test_file.exists()
    import json

    with open(test_file) as f:
        loaded = json.load(f)
    assert loaded == data


def test_datasync_uses_fdatasync_when_available_and_not_darwin(monkeypatch):
    calls = {"fdatasync": 0, "fsync": 0}

    dummy_os = SimpleNamespace(
        fdatasync=lambda fd: calls.__setitem__("fdatasync", calls["fdatasync"] + 1),
        fsync=lambda fd: calls.__setitem__("fsync", calls["fsync"] + 1),
    )
    dummy_platform = SimpleNamespace(system=lambda: "Linux")

    monkeypatch.setattr(utils_file, "os", dummy_os)
    monkeypatch.setattr(utils_file, "platform", dummy_platform)

    utils_file.datasync(123)

    assert calls["fdatasync"] == 1
    assert calls["fsync"] == 0


def test_datasync_uses_fsync_on_darwin_even_if_fdatasync_exists(monkeypatch):
    calls = {"fdatasync": 0, "fsync": 0}

    dummy_os = SimpleNamespace(
        fdatasync=lambda fd: calls.__setitem__("fdatasync", calls["fdatasync"] + 1),
        fsync=lambda fd: calls.__setitem__("fsync", calls["fsync"] + 1),
    )
    dummy_platform = SimpleNamespace(system=lambda: "Darwin")

    monkeypatch.setattr(utils_file, "os", dummy_os)
    monkeypatch.setattr(utils_file, "platform", dummy_platform)

    utils_file.datasync(123)

    assert calls["fdatasync"] == 0
    assert calls["fsync"] == 1


def test_datasync_falls_back_to_fsync_when_fdatasync_missing(monkeypatch):
    calls = {"fsync": 0}

    dummy_os = SimpleNamespace(
        fsync=lambda fd: calls.__setitem__("fsync", calls["fsync"] + 1),
    )
    dummy_platform = SimpleNamespace(system=lambda: "Linux")

    monkeypatch.setattr(utils_file, "os", dummy_os)
    monkeypatch.setattr(utils_file, "platform", dummy_platform)

    utils_file.datasync(123)

    assert calls["fsync"] == 1
