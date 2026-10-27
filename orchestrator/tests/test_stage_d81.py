"""P13 / ST1 (D81): the stage document — invariants, the store's revision guard, and the routes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.stages import Stage, StageCamera, StageObject, StageStore, StaleStage, check  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def obj(i: str, **kw) -> StageObject:
    return StageObject(id=i, kind=kw.pop("kind", "prop"), name=kw.pop("name", i), **kw)


def test_invariants():
    check(Stage(id="s", objects=[obj("a"), obj("b", parent="a")], cameras=[StageCamera(id="c")], active_camera="c"))
    with pytest.raises(ValueError, match="unique"):
        check(Stage(id="s", objects=[obj("a"), obj("a")]))
    with pytest.raises(ValueError, match="not in the stage"):
        check(Stage(id="s", objects=[obj("a", parent="zz")]))
    with pytest.raises(ValueError, match="cycle"):
        check(Stage(id="s", objects=[obj("a", parent="b"), obj("b", parent="a")]))
    with pytest.raises(ValueError, match="active camera"):
        check(Stage(id="s", cameras=[StageCamera(id="c")], active_camera="d"))
    with pytest.raises(ValueError, match="out of range"):
        check(Stage(id="s", cameras=[StageCamera(id="c", focal_mm=2.0)]))
    with pytest.raises(ValueError, match="three components"):
        check(Stage(id="s", objects=[StageObject(id="a", kind="prop", name="a", transform={"pos": [0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]})]))


def test_store_create_put_revision_delete(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StageStore(ws)
    s = st.create("Alley", {"w": 1280, "h": 720, "fps": 24})
    assert s.revision == 0 and len(s.cameras) == 1 and s.active_camera == s.cameras[0].id and s.cameras[0].focal_mm == 35.0 and s.cameras[0].sensor_mm == 36.0
    assert st.get(s.id) == s and [x.id for x in st.list()] == [s.id]
    body = {**s.model_dump(), "objects": [{"id": "m1", "kind": "mannequin", "name": "Ada", "preset": "adult", "pose": {"preset": "stand"}}]}
    s1 = st.put(s.id, body)
    assert s1.revision == 1 and s1.objects[0].pose.preset == "stand" and s1.objects[0].transform.pos == [0.0, 0.0, 0.0]
    with pytest.raises(StaleStage):
        st.put(s.id, body)                                                   # based on revision 0 again
    with pytest.raises(ValueError):
        st.put(s.id, {**body, "revision": 1, "active_camera": "nope"})
    assert st.get(s.id).revision == 1
    assert st.delete(s.id) and st.get(s.id) is None and not st.delete(s.id)


def test_routes(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        assert cl.get("/stages", headers=H).status_code == 409
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        s = cl.post("/stages", json={"name": "Alley"}, headers=H).json()
        assert s["size"] == {"w": 1920, "h": 1080, "fps": 24} and s["revision"] == 0 and len(s["cameras"]) == 1
        assert [x["id"] for x in cl.get("/stages", headers=H).json()["items"]] == [s["id"]]
        body = {**s, "objects": [{"id": "m1", "kind": "mannequin", "name": "Ada", "transform": {"pos": [1, 0, 0], "rot": [0, 30, 0], "scale": [1, 1, 1]}}],
                "cameras": [{**s["cameras"][0], "focal_mm": 50}]}
        r = cl.put(f"/stages/{s['id']}", json=body, headers=H)
        assert r.status_code == 200 and r.json()["revision"] == 1 and r.json()["cameras"][0]["focal_mm"] == 50
        assert cl.put(f"/stages/{s['id']}", json=body, headers=H).status_code == 409
        assert cl.put(f"/stages/{s['id']}", json={**body, "revision": 1, "objects": [{"id": "x", "kind": "prop", "name": "x", "parent": "ghost"}]}, headers=H).status_code == 422
        assert cl.get(f"/stages/{s['id']}", headers=H).json()["objects"][0]["name"] == "Ada"
        assert cl.delete(f"/stages/{s['id']}", headers=H).json()["deleted"] == s["id"]
        assert cl.get(f"/stages/{s['id']}", headers=H).status_code == 404


def test_pose_library_routes(tmp_path: Path):
    """ST2: the project's saved poses round-trip; a malformed joint list is refused."""
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        assert cl.get("/stages/poses", headers=H).json()["poses"] == {}
        lib = {"poses": {"salute": {"preset": "stand", "joints": {"r_shoulder": [-150, 0, -20], "r_elbow": [-120, 0, 0]}}}}
        assert cl.put("/stages/poses", json=lib, headers=H).status_code == 200
        assert cl.get("/stages/poses", headers=H).json()["poses"] == lib["poses"]
        assert cl.put("/stages/poses", json={"poses": {"bad": {"joints": {"head": [1, 2]}}}}, headers=H).status_code == 422
        assert (Workspace(tmp_path / "proj").stages_dir / "poses.json").is_file()
        # the literal route is not shadowed by /stages/{st_id}
        assert cl.get("/stages/poses", headers=H).status_code == 200
