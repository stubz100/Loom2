import json
from pathlib import Path

import pytest

from loom2 import fsio
from loom2.config import AppState
from loom2.workspace import ProjectFormat, Workspace


def test_atomic_write_and_refusing_reader(tmp_path: Path):
    p = tmp_path / "rec.json"
    fsio.atomic_write_json(p, {"a": 1})
    assert fsio.read_json(p) == {"a": 1}
    assert not list(tmp_path.glob("*.tmp"))
    p.write_text('{"a": 1', encoding="utf-8")          # a torn record
    with pytest.raises(fsio.StateError):
        fsio.read_json(p)
    with pytest.raises(fsio.StateError):
        fsio.read_json(tmp_path / "missing.json")
    assert fsio.read_json_or(tmp_path / "missing.json", {"d": True}) == {"d": True}


def test_ids_and_slugs():
    a, b = fsio.new_id("ast"), fsio.new_id("ast")
    assert a.startswith("ast_") and a != b and len(a) == 4 + 8
    assert fsio.slugify("  Hello, World! ") == "hello-world"
    assert fsio.slugify("***") == "item"


def test_workspace_create_open(tmp_path: Path):
    ws = Workspace.create(tmp_path / "proj", name="Test", size_cap_gb=10)
    assert ws.project_json.is_file()
    for sub in ("assets", "thumbs", "documents", "clips", "masks", "jobs/logs", "_temp"):      # engine_out moved to <app state> (06 §4, B6)
        assert (ws.path / sub).is_dir()
    rec = ws.load()
    assert rec.name == "Test" and rec.format.width == 1920 and rec.format.default_tier == "draft"
    again = Workspace.open(tmp_path / "proj")
    assert again.load().id == rec.id
    info = again.info()
    assert info["open"] and info["name"] == "Test" and info["free_space_gb"] > 0


def test_workspace_refuses_bad_input(tmp_path: Path):
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "file.txt").write_text("x")
    with pytest.raises(fsio.StateError):
        Workspace.create(tmp_path / "busy", name="X", size_cap_gb=10)
    with pytest.raises(fsio.StateError):
        Workspace.create(tmp_path / "p2", name="   ", size_cap_gb=10)
    with pytest.raises(fsio.StateError):
        Workspace.create(tmp_path / "p3", name="X", size_cap_gb=10, fmt={"aspect": [1, 1], "width": 1920, "height": 1080, "fps": 24})
    with pytest.raises(fsio.StateError):
        Workspace.open(tmp_path / "nowhere")


def test_project_format_geometry_lock():
    ProjectFormat(aspect=(16, 9), width=1280, height=720)
    with pytest.raises(ValueError):
        ProjectFormat(aspect=(4, 3), width=1920, height=1080)


def test_app_state_settings_roundtrip(tmp_path: Path):
    app = AppState(tmp_path / "state")
    assert app.app_json.parent.is_dir() and len(app.token) > 20
    app.update_settings({"vram_budget_gb": 12, "engine": {"port": 8199}})
    app2 = AppState(tmp_path / "state")
    assert app2.settings.vram_budget_gb == 12 and app2.settings.engine.port == 8199
    assert app2.settings.engine.host == "127.0.0.1"      # untouched nested defaults survive the merge
    app2.touch_project(tmp_path / "p1")
    app2.touch_project(tmp_path / "p2")
    app2.touch_project(tmp_path / "p1")
    rec = json.loads(app2.app_json.read_text(encoding="utf-8"))
    assert rec["last_project"].endswith("p1") and len(rec["recents"]) == 2
