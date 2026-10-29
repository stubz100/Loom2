"""U2 (D157, G6 + G12; proto01_UI2 04 §1, 06 §2.3): a scene owns its stage and a shot is a camera of its own on it over a range.

- a camera serves one shot: linking a second shot to it (Link a stage camera, New shot from this camera) gives that shot a copy;
- a shot linked to a stage claims it for its scene when the scene has none; New Shot from this Shot keeps the scene's stage;
- a version's range is {start, end} on the scene's timeline;
- a book of schema 1 is migrated once: a scene whose Shots look at one stage owns it;
- POST /story/flow/shots makes the node, its scene, the scene's stage and its camera in one call — a new scene (from a place's set or empty)
  or the same scene as the shot before (a new camera) — placed and connected after the shot before.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loom2.api import create_app
from loom2.config import AppState
from loom2.fsio import atomic_write_json, read_json
from loom2.stages import StageStore
from loom2.story import StoryStore
from loom2.workspace import Workspace


def test_a_camera_serves_one_shot(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    stg = stages.create("Quay")
    cam = stg.cameras[0]
    a = st.create_node("shot", "Wide")
    st.set_source(a.shot_id, "v1", stg.id, cam.id, stg.revision)
    assert st.shot(a.shot_id).version().camera_id == cam.id                          # free: its own
    b = st.create_node("shot", "Close")
    sb = st.set_source(b.shot_id, "v1", stg.id, cam.id, stg.revision)
    after = stages.get(stg.id)
    assert sb.version().camera_id != cam.id and sb.version().camera_id in [c.id for c in after.cameras]   # taken: a copy for this one
    assert [c.name for c in after.cameras] == ["Camera 1", "Camera 1 2"] and sb.version().stage_revision == after.revision
    again = st.set_source(b.shot_id, "v1", stg.id, sb.version().camera_id, after.revision)        # its own camera again: no new copy
    assert again.version().camera_id == sb.version().camera_id and len(stages.get(stg.id).cameras) == 2
    made = st.create_shot("From the camera", stage_id=stg.id, camera_id=cam.id, stage_revision=after.revision)   # New shot from this camera
    assert made.version().camera_id not in (cam.id, sb.version().camera_id) and len(stages.get(stg.id).cameras) == 3
    with pytest.raises(ValueError, match="range"):
        st.patch_shot(a.shot_id, {"revision": st.shot(a.shot_id).revision, "versions": [{"id": "v1", "range": {"start": 30, "end": 10}}]})
    ranged = st.patch_shot(a.shot_id, {"revision": st.shot(a.shot_id).revision, "versions": [{"id": "v1", "range": {"start": 0, "end": 47}}]})
    assert ranged.version().range == {"start": 0, "end": 47}


def test_a_scene_owns_the_stage_its_shots_look_at(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    stg = stages.create("Quay")
    a = st.create_node("shot", "Wide")
    scn = st.create_scene("At the quay", [a.id])
    st.set_source(a.shot_id, "v1", stg.id, stg.cameras[0].id, stg.revision)
    assert next(s for s in st.scene_book().scenes if s.id == scn.id).stage_id == stg.id
    sib = st.new_shot_from(a.id)                                                       # New Shot from this Shot: same scene, a camera of its own
    v = st.shot(sib.shot_id).version()
    assert sib.scene_id == scn.id and v.stage_id == stg.id and v.camera_id != stg.cameras[0].id
    # the migration: a book of schema 1 — a scene whose Shots are on one stage owns it, one with none or two stages keeps none
    b = st.create_node("shot", "Elsewhere")
    other = st.create_scene("Nowhere", [b.id])
    book = read_json(ws.story_dir / "flow" / "scenes.json")
    for s in book["scenes"]:
        s.pop("stage_id", None)
    atomic_write_json(ws.story_dir / "flow" / "scenes.json", {**book, "schema_version": 1})
    again = StoryStore(ws)
    assert again.migrated == ["U2: 1 scene owns its stage now"]
    by_id = {s.id: s for s in again.scene_book().scenes}
    assert by_id[scn.id].stage_id == stg.id and by_id[other.id].stage_id is None
    assert read_json(ws.story_dir / "flow" / "scenes.json")["schema_version"] == 2 and StoryStore(ws).migrated == []   # once


def _client(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    return app, TestClient(app, headers={"X-Loom-Token": app.state.services.app.token})


def test_new_shot_in_one_call(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ws = Workspace(tmp_path / "p")
        first = cl.post("/story/flow/shots", json={"title": "The ferry leaves"}).json()        # a new scene, an empty stage
        v1 = cl.get(f"/story/shots/{first['shot_id']}").json()["versions"][0]
        stage = StageStore(ws).get(v1["stage_id"])
        assert stage is not None and stage.name == "The ferry leaves" and v1["camera_id"] == stage.cameras[0].id
        scenes = {s["name"]: s for s in cl.get("/story/scenes").json()["items"]}
        assert scenes["The ferry leaves"]["stage_id"] == stage.id and scenes["The ferry leaves"]["node_ids"] == [first["id"]]
        third = cl.post("/story/flow/shots", json={"title": "Later", "after": first["id"]}).json()
        cover = cl.post("/story/flow/shots", json={"title": "Close on Ines", "after": first["id"], "scene": "same"}).json()   # coverage
        vc = cl.get(f"/story/shots/{cover['shot_id']}").json()["versions"][0]
        assert vc["stage_id"] == stage.id and vc["camera_id"] != v1["camera_id"] and len(StageStore(ws).get(stage.id).cameras) == 2
        assert cover["scene_id"] == first["scene_id"] and third["scene_id"] != first["scene_id"]
        edges = {(e["from"], e["to"]) for e in cl.get("/story/flow").json()["graph"]["edges"]}
        assert edges == {(first["id"], cover["id"]), (cover["id"], third["id"])}          # put between the shot and the one it led to
        assert cl.post("/story/flow/shots", json={"after": "node_nope"}).status_code == 404
        bare = cl.post("/story/flow/nodes", json={"type": "shot", "title": "No stage"}).json()
        assert cl.post("/story/flow/shots", json={"after": bare["id"], "scene": "same"}).status_code == 422   # no scene on a stage to share
        assert cl.post("/story/flow/shots", json={"place_id": first["id"]}).status_code == 422            # not a World place
