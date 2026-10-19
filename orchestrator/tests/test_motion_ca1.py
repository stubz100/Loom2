"""CA1 (proto01_animate 02 §5): the motion library's files — the starter set's glb files (its fbx copies and `_downloads` skipped) and the
local folder's glb / gltf / fbx, listed with a licence line and served by id; a missing folder lists nothing. The test rig is
tests/fixtures/motion/test_rig.glb (scripts/make_motion_fixture.py) — never a Mixamo file."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.motion import resolve, scan  # noqa: E402

RIG = Path(__file__).parent / "fixtures" / "motion" / "test_rig.glb"


def _folders(tmp: Path) -> tuple[Path, Path]:
    starter, local = tmp / "motion", tmp / "mine"
    (starter / "pack" / "Godot").mkdir(parents=True)
    shutil.copyfile(RIG, starter / "pack" / "Godot" / "rig.glb")
    (starter / "pack" / "Unity").mkdir()
    (starter / "pack" / "Unity" / "rig.fbx").write_bytes(b"fbx")                  # the same clips as fbx: not listed from the starter set
    (starter / "_downloads").mkdir()
    shutil.copyfile(RIG, starter / "_downloads" / "zipped.glb")                    # never listed
    local.mkdir()
    (local / "Walking.fbx").write_bytes(b"Kaydara FBX Binary")
    (local / "notes.txt").write_text("x")
    return starter, local


def test_scan_and_resolve(tmp_path: Path):
    starter, local = _folders(tmp_path)
    files = scan(starter, local)
    assert [(f.source, f.rel, f.ext) for f in files] == [("starter", "pack/Godot/rig.glb", "glb"), ("local", "Walking.fbx", "fbx")]
    assert files[0].licence.startswith("CC0") and "never bundled" in files[1].licence and files[0].bytes == RIG.stat().st_size
    assert resolve(files[1].id, starter, local) == local / "Walking.fbx"
    assert scan(starter, local)[0].id == files[0].id                               # stable ids
    assert scan(None, tmp_path / "gone") == [] and resolve("mot_nope", starter, local) is None


def test_routes(tmp_path: Path):
    starter, local = _folders(tmp_path)
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "motion": {"starter_dir": str(starter), "local_dir": ""}})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        r = cl.get("/motion/files").json()
        assert [f["source"] for f in r["items"]] == ["starter"] and r["local_dir"] is None and r["starter_dir"] == str(starter)
        assert cl.get(f"/motion/files/{r['items'][0]['id']}").content == RIG.read_bytes()
        assert cl.get("/motion/files/mot_nope").status_code == 404
        s = cl.get("/settings").json()
        assert cl.put("/settings", json={**s, "motion": {"starter_dir": str(starter), "local_dir": str(local)}}).status_code == 200
        r = cl.get("/motion/files").json()
        assert [f["name"] for f in r["items"]] == ["rig", "Walking"] and r["local_dir"] == str(local)
        # the default starter folder is <models_root>/motion
        cl.put("/settings", json={**cl.get("/settings").json(), "motion": {"starter_dir": "", "local_dir": ""}})
        assert cl.get("/motion/files").json()["starter_dir"] is None
