"""RC2c (D96, proto01_animate 31 §3a): scene groups — a frame around Shots in the Flow, kept as `story/flow/scenes.json` with the members
named by the nodes; made around nodes (they leave their old scene), joined, left, renamed, dissolved (the nodes stay); a scene left empty
goes. *New Shot from this Shot* (O2) makes a sibling in the scene — the stage, the place and the pins shared, the lines and a camera of its
own (the source's copied with its keys) — and makes the scene when the source has none. CE4's *Grade the scene* takes the scene group."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.stages import StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def test_scenes_in_the_store(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    a, b, c = (st.create_node("dialogue", t, 0, 200 * i) for i, t in enumerate(("Wide", "Mara", "Ines")))
    s = st.create_scene("The quay", [a.id, b.id])
    assert [x["node_ids"] for x in st.scenes()] == [[a.id, b.id]] and st.flow_node(a.id).scene_id == s.id
    with pytest.raises(ValueError, match="needs a name"):
        st.create_scene("  ", [c.id])
    with pytest.raises(KeyError):
        st.create_scene("Gone", ["node_nope"])
    st.scene_members(s.id, [c.id], [])
    assert st.scenes()[0]["node_ids"] == [a.id, b.id, c.id]                                   # in the Flow's reading order
    t = st.create_scene("Inside", [c.id])                                                    # it leaves the quay for the new scene
    assert {x["name"]: x["node_ids"] for x in st.scenes()} == {"The quay": [a.id, b.id], "Inside": [c.id]}
    st.patch_scene(t.id, {"name": "The shed"})
    st.scene_members(t.id, [], [c.id])                                                       # left empty: it goes
    assert [x["name"] for x in st.scenes()] == ["The quay"] and all(x.id != t.id for x in st.scene_book().scenes)
    st.delete_node(b.id, delete_shot=True)
    assert st.scenes()[0]["node_ids"] == [a.id]
    assert st.delete_scene(s.id) and st.flow_node(a.id).scene_id is None and st.scenes() == [] and not st.delete_scene(s.id)


def test_new_shot_from_this_shot(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    stages = StageStore(ws)
    stg = stages.create("Quay", {"w": 64, "h": 64, "fps": 24})
    cam = stg.cameras[0]
    stg = stages.put(stg.id, {"revision": stg.revision, "keyframes": {"camera": {cam.id: [{"f": 0, "pos": [0, 1.5, 4]}, {"f": 48, "pos": [1, 1.5, 3]}]}, "objects": {}}})
    src = st.create_node("dialogue", "Talk", 100, 100, lines=[{"speaker": None, "text": "Hi.", "audio_asset_id": "ast_line", "audio_text": "Hi."}])
    st.set_source(src.shot_id, "v1", stg.id, cam.id, stg.revision)
    st.add_take(src.shot_id, "v1", "image", "ast_frame")
    st.patch_node(src.id, {"speaker_versions": {"prf_mara": "v2"}})
    sib = st.new_shot_from(src.id)
    assert sib.type == "dialogue" and sib.title == "Talk · 2" and sib.lines[0].text == "Hi." and sib.lines[0].audio_asset_id == "ast_line"
    assert sib.speaker_versions == {"prf_mara": "v2"} and sib.shot_id and sib.shot_id != src.shot_id
    v = st.shot(sib.shot_id).version()
    assert v.stage_id == stg.id and v.camera_id not in (None, cam.id) and v.takes == [] and v.frame_asset_id is None   # the stage shared, its own camera
    stg2 = stages.get(stg.id)
    new_cam = next(c for c in stg2.cameras if c.id == v.camera_id)
    assert new_cam.name == f"{cam.name} 2" and new_cam.pos == cam.pos and stg2.keyframes["camera"][new_cam.id] == stg2.keyframes["camera"][cam.id]
    assert v.stage_revision == stg2.revision
    scenes = st.scenes()                                                                     # a scene was made around the two
    assert len(scenes) == 1 and scenes[0]["name"] == "Talk" and set(scenes[0]["node_ids"]) == {src.id, sib.id}
    third = st.new_shot_from(src.id)                                                         # the next sibling joins the same scene, below
    assert third.title == "Talk · 3" and st.flow_node(third.id).scene_id == scenes[0]["id"]
    g = {p.id: p for p in st.flow_graph().nodes}
    assert g[sib.id].x == g[src.id].x and g[sib.id].y > g[src.id].y and g[third.id].y > g[sib.id].y
    with pytest.raises(ValueError):
        st.new_shot_from(st.create_node("choice", "Pick").id)


def test_routes(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "q"), "name": "q", "size_cap_gb": 10}).status_code == 200
        a = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Wide"}).json()
        b = cl.post("/story/flow/nodes", json={"type": "shot", "title": "Close"}).json()
        r = cl.post("/story/scenes", json={"name": "Quay", "node_ids": [a["id"]]})
        assert r.status_code == 200 and r.json()["items"][0]["node_ids"] == [a["id"]]
        sid, rev = r.json()["items"][0]["id"], r.json()["revision"]
        assert cl.post("/story/scenes", json={"name": "x", "node_ids": ["node_nope"]}).status_code == 404
        assert cl.post(f"/story/scenes/{sid}/nodes", json={"add": [b["id"]]}).json()["items"][0]["node_ids"] == [a["id"], b["id"]]
        r = cl.patch(f"/story/scenes/{sid}", json={"revision": rev, "name": "The quay"})
        assert r.status_code == 200 and r.json()["items"][0]["name"] == "The quay"
        assert cl.patch(f"/story/scenes/{sid}", json={"revision": rev, "name": "x"}).status_code == 409             # based on the old revision
        assert cl.get("/story/flow").json()["nodes"][0]["scene_id"] == sid
        s = cl.post(f"/story/flow/nodes/{a['id']}/sibling")
        assert s.status_code == 200 and s.json()["scene_id"] == sid and s.json()["title"] == "Wide · 2"
        assert cl.post(f"/story/flow/nodes/{s.json()['id']}/sibling").json()["title"] == "Wide · 3"
        assert cl.delete(f"/story/scenes/{sid}").status_code == 200 and cl.get("/story/scenes").json()["items"] == []
        assert cl.delete(f"/story/scenes/{sid}").status_code == 404
