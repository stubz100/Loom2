"""RC2e (06 O2, proto01_animate 31 §3a): Shot templates — *Save as a template…* keeps a Shot's kind, lines (the words, not the voice), line,
route and camera with its keys in `story/shot_templates.json`; *New Shot from a template* places a node of that kind on that route — beside a
node it joins the node's scene and place and gets the template's camera on that node's stage; at a point, a bare start. Renamed, deleted."""
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


def test_templates_in_the_store(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    stg = stages.create("Quay", {"w": 64, "h": 64, "fps": 24})
    cam = stg.cameras[0]
    stg = stages.put(stg.id, {"revision": stg.revision, "cameras": [{**cam.model_dump(), "focal_mm": 85.0, "pos": [0.5, 1.6, 1.2]}],
                              "keyframes": {"camera": {cam.id: [{"f": 0, "pos": [0.5, 1.6, 1.2]}]}, "objects": {}}})
    src = st.create_node("dialogue", "Close-up", lines=[{"speaker": "prf_mara", "text": "Not now.", "audio_asset_id": "ast_v", "audio_text": "Not now."}])
    st.set_source(src.shot_id, "v1", stg.id, cam.id, stg.revision)
    t = st.save_shot_template(src.id, "Close-up from the wide")
    assert t.node_type == "shot" and t.route == "stage" and [(ln.speaker, ln.text) for ln in t.lines] == [("prf_mara", "Not now.")]
    assert t.camera is not None and t.camera.focal_mm == 85.0 and t.camera.pos == [0.5, 1.6, 1.2] and len(t.camera.keys) == 1
    with pytest.raises(ValueError, match="needs a name"):
        st.save_shot_template(src.id, " ")
    with pytest.raises(ValueError):
        st.save_shot_template(st.create_node("choice", "Pick").id, "x")
    # beside a node in a scene on a stage: it joins the scene and the place, its camera on that stage
    wide = st.create_node("shot", "Wide", 0, 0)
    st.set_source(wide.shot_id, "v1", stg.id, cam.id, stages.get(stg.id).revision)
    scene = st.create_scene("The quay", [wide.id])
    n = st.new_shot_from_template(t.id, near=wide.id)
    assert n.type == "shot" and n.title == "Close-up from the wide" and n.lines[0].text == "Not now." and n.lines[0].audio_asset_id is None
    assert n.scene_id == scene.id
    v = st.shot(n.shot_id).version()
    after = stages.get(stg.id)
    made = next(c for c in after.cameras if c.id == v.camera_id)
    assert v.stage_id == stg.id and made.focal_mm == 85.0 and made.name != cam.name and after.keyframes["camera"][made.id] == [{"f": 0, "pos": [0.5, 1.6, 1.2]}]
    assert v.recipe is not None and v.recipe.template == "stage"
    # at a point: a bare start (no scene, no stage)
    m = st.new_shot_from_template(t.id, x=900, y=40)
    assert m.scene_id is None and st.shot(m.shot_id).version().stage_id is None
    assert next(p for p in st.flow_graph().nodes if p.id == m.id).x == 900
    st.rename_shot_template(t.id, "Close-up")
    assert [x.name for x in st.shot_templates().templates] == ["Close-up"]
    assert st.delete_shot_template(t.id) and st.shot_templates().templates == [] and not st.delete_shot_template(t.id)
    with pytest.raises(KeyError):
        st.new_shot_from_template(t.id)


def test_template_routes(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "q"), "name": "q", "size_cap_gb": 10}).status_code == 200
        a = cl.post("/story/flow/nodes", json={"type": "shot", "title": "Walk-in"}).json()
        r = cl.post("/story/shot-templates", json={"node_id": a["id"], "name": "Walk-in wide"})
        assert r.status_code == 200 and r.json()["items"][0]["route"] == "i2v" and r.json()["items"][0]["camera"] is None
        tid = r.json()["items"][0]["id"]
        assert cl.post("/story/shot-templates", json={"node_id": "node_nope", "name": "x"}).status_code == 404
        assert cl.patch(f"/story/shot-templates/{tid}", json={"node_id": "", "name": "Walk-in"}).json()["items"][0]["name"] == "Walk-in"
        n = cl.post(f"/story/shot-templates/{tid}/use", json={"near": a["id"]})
        assert n.status_code == 200 and n.json()["type"] == "shot" and n.json()["title"] == "Walk-in"
        assert cl.post(f"/story/shot-templates/{tid}/use", json={"near": "node_nope"}).status_code == 404
        assert cl.delete(f"/story/shot-templates/{tid}").status_code == 200 and cl.get("/story/shot-templates").json()["items"] == []
