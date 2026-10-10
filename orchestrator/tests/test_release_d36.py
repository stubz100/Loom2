"""D36 release hygiene: one VERSION for every location (scripts/bump_version.py), build facts in /version."""
import importlib.util
import shutil
import sys
from pathlib import Path

from loom2 import build_info
from loom2.config import REPO_ROOT

from test_api import _client


def _bump_module():
    spec = importlib.util.spec_from_file_location("bump_version", REPO_ROOT / "scripts" / "bump_version.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod                                              # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


def _copy_version_files(bump, root: Path) -> None:
    for loc in bump.LOCATIONS:
        dst = root / loc.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / loc.path, dst)


def test_repository_versions_agree():
    bump = _bump_module()
    assert bump.mismatches() == []                                            # what CI checks on every push


def test_bump_rewrites_every_location_and_check_catches_drift(tmp_path: Path):
    bump = _bump_module()
    _copy_version_files(bump, tmp_path)
    changed = bump.write_version("1.2.3", root=tmp_path)
    assert set(changed) == {loc.path for loc in bump.LOCATIONS}
    assert bump.mismatches(tmp_path) == []
    assert {v for _, v in bump.read_versions(tmp_path)} == {"1.2.3"}
    lock = (tmp_path / "frontend/package-lock.json").read_text(encoding="utf-8")
    assert lock.count('"version": "1.2.3"') == 2                              # root and packages[""], no dependency touched
    cargo = tmp_path / "frontend/src-tauri/Cargo.toml"
    cargo.write_text(cargo.read_text(encoding="utf-8").replace('version = "1.2.3"', 'version = "9.9.9"', 1), encoding="utf-8")
    assert bump.mismatches(tmp_path) == ["frontend/src-tauri/Cargo.toml: '9.9.9' (VERSION says 1.2.3)"]
    assert bump.bumped("1.2.3", "patch") == "1.2.4" and bump.bumped("1.2.3", "minor") == "1.3.0" and bump.bumped("1.2.3", "major") == "2.0.0"


def test_shell_build_facts_come_from_the_environment(monkeypatch):
    monkeypatch.delenv("LOOM2_SHELL_VERSION", raising=False)
    assert build_info.shell_info() is None                                    # browser dev: no shell
    monkeypatch.setenv("LOOM2_SHELL_VERSION", "0.1.0")
    monkeypatch.setenv("LOOM2_SHELL_GIT_SHA", "abc1234")
    monkeypatch.setenv("LOOM2_SHELL_BUILD_EPOCH", "1760000000")
    assert build_info.shell_info() == {"version": "0.1.0", "git_sha": "abc1234", "build_time": "2025-10-09T08:53:20+00:00"}


def test_node_pins_and_version_endpoint(tmp_path: Path):
    pins = build_info.node_pins()
    assert [p["name"] for p in pins] == ["ComfyUI-GGUF", "LanPaint"]           # engine/nodes.lock, patches line ignored
    client, _ = _client(tmp_path)
    with client:
        v = client.get("/version").json()
    assert v["app"] == build_info.app_version() and v["variant"] == "full"
    assert set(v) >= {"app", "orchestrator", "git", "shell", "engine", "nodes", "schemas", "paths", "variant"}
    assert "engine_pin" not in v and set(v["engine"]) == {"pin", "running"} and v["engine"]["running"] is None
    assert v["schemas"]["queue"] >= 1 and v["schemas"]["index"] >= 2
    assert v["paths"]["state"].endswith("state")
