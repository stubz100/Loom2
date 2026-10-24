"""RC2f (06 O3, proto01_animate 31 §3b): within a scene a Shot's parts are linked by default, each with *Make independent* — the Cast pins
are the scene's (a linked Shot wears them, and a change on it is the scene's, merged as a change so another Shot's edit is not undone; a
Shot keeps its own when asked, or when it joined with pins of its own that differ), the stage is shared (a copy for one version when asked),
and the scene's grade in the cut (a shot leaves the scene's adjustment layer with the scene's Lumetri as its own)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.stages import StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_filmcraft.py"


def test_the_cast_is_the_scenes(tmp_path: Path):
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    a = st.create_node("dialogue", "Wide")
    st.patch_node(a.id, {"speaker_versions": {"prf_mara": "v2"}})
    sib = st.new_shot_from(a.id)                                                    # the scene made around a takes a's pins
    assert st.flow_node(sib.id).speaker_versions == {"prf_mara": "v2"} and st.scenes()[0]["cast_versions"] == {"prf_mara": "v2"}
    st.patch_node(sib.id, {"speaker_versions": {"prf_mara": "v3"}})                 # on a linked Shot: the scene's
    assert st.flow_node(a.id).speaker_versions == {"prf_mara": "v3"}
    # a change is merged into the scene's pins as a change (a key set or taken away); a title edit leaves them alone
    st.patch_node(sib.id, {"speaker_versions": {"prf_mara": "v3", "prf_ines": "v1"}})
    st.patch_node(a.id, {"title": "Wide · dusk"})
    assert st.flow_node(sib.id).speaker_versions == {"prf_mara": "v3", "prf_ines": "v1"} and st.scene_book().scenes[0].cast_versions == {"prf_mara": "v3", "prf_ines": "v1"}
    assert st._record(sib.id).speaker_versions == {}                                # a linked Shot keeps none of its own
    # Make independent: its own from now on; a change on it stays its own
    own = st.own_part(sib.id, "cast", True)
    assert own.own == ["cast"] and own.speaker_versions == {"prf_mara": "v3", "prf_ines": "v1"}
    st.patch_node(sib.id, {"speaker_versions": {"prf_mara": "v1"}})
    assert st.flow_node(a.id).speaker_versions == {"prf_mara": "v3", "prf_ines": "v1"} and st.flow_node(sib.id).speaker_versions == {"prf_mara": "v1"}
    back = st.own_part(sib.id, "cast", False)                                       # the scene's again
    assert back.own == [] and back.speaker_versions == {"prf_mara": "v3", "prf_ines": "v1"}
    # a node joining with pins that differ keeps them as its own; one with none is linked; one leaving keeps the scene's as its own
    c = st.create_node("shot", "Close")
    st.patch_node(c.id, {"speaker_versions": {"prf_mara": "v9"}})
    d = st.create_node("shot", "Insert")
    sid = st.scenes()[0]["id"]
    st.scene_members(sid, [c.id, d.id], [])
    assert st.flow_node(c.id).own == ["cast"] and st.flow_node(c.id).speaker_versions == {"prf_mara": "v9"}
    assert st.flow_node(d.id).own == [] and st.flow_node(d.id).speaker_versions == {"prf_mara": "v3", "prf_ines": "v1"}
    st.scene_members(sid, [], [d.id])
    assert st.flow_node(d.id).speaker_versions == {"prf_mara": "v3", "prf_ines": "v1"} and st.flow_node(d.id).scene_id is None
    with pytest.raises(ValueError, match="in no scene"):
        st.own_part(d.id, "cast", True)


def test_a_stage_of_its_own(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    stg = stages.create("Quay", {"w": 64, "h": 64, "fps": 24})
    cam = stg.cameras[0]
    stg = stages.put(stg.id, {"revision": stg.revision, "objects": [{"id": "obj_crate", "kind": "prop", "name": "Crate", "preset": "crate"}],
                              "keyframes": {"camera": {cam.id: [{"f": 0}]}, "objects": {}}})
    a = st.create_node("shot", "Wide")
    st.set_source(a.shot_id, "v1", stg.id, cam.id, stg.revision)
    b = st.new_shot_from(a.id)                                                      # shares the stage, its own camera
    s = st.own_stage(b.shot_id, "v1")
    v = s.version()
    copy = stages.get(v.stage_id)
    assert v.stage_id != stg.id and v.camera_id in [c.id for c in copy.cameras] and [o.id for o in copy.objects] == ["obj_crate"]
    assert copy.name == "Quay · Wide · 2" and copy.keyframes["camera"][cam.id] == [{"f": 0}] and copy.passes == []
    assert st.shot(a.shot_id).version().stage_id == stg.id                          # the other Shot keeps the shared one
    with pytest.raises(ValueError, match="no stage"):
        st.own_stage(st.create_node("shot", "Bare").shot_id, "v1")


def test_a_grade_of_its_own(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(FAKE), "timeout_s": 20.0}})
    app = create_app(state)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        cs, st = ClipStore(ws), StoryStore(ws)
        frames = []
        for i in range(24):
            f = tmp_path / f"f{i}.png"
            Image.new("RGB", (32, 24), (180, 90, 40)).save(f)
            frames.append(f)
        clip = cs.encode_proxy(cs.create(frames, model_id="wan22-i2v-high-fp8", prompt="s", seed=1, fps=24, start_asset_id="ast_x"))
        nodes = [st.create_node("dialogue", title=t, with_shot=False) for t in ("In", "Through", "Out")]
        st.create_scene("The gate", [n.id for n in nodes])
        tl = cl.post("/timelines", json={"name": "Colour", "fps": 24, "w": 64, "h": 36}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": str(k), "clip_id": clip.id, "in": 0, "out": 24, "node_id": n.id} for k, n in enumerate(nodes)],
                                                    "overlaps": [0, 0, 0]}).json()
        base = f"/timelines/{tl['id']}"
        v1 = cl.get(f"{base}/tracks").json()["video"][0]["items"]
        r = cl.post(f"{base}/grade/scene", json={"clip": v1[0]["id"]}).json()
        layer = r["results"][0]["clip"]
        assert r["results"][0]["shots"] == 3
        cl.post(f"{base}/grade", json={"clip": layer, "values": {"exposure": 1.5}})
        assert cl.post(f"{base}/grade/own", json={"clip": v1[0]["id"] + 999}).status_code == 422
        r = cl.post(f"{base}/grade/own", json={"clip": v1[1]["id"]})                 # the middle shot leaves the scene's grade
        assert r.status_code == 200, r.text
        tracks = r.json()["tracks"]
        grade = tracks["video"][-1]["items"]
        spans = sorted((i["start"], i["start"] + i["duration"]) for i in grade)
        assert spans == [(v1[0]["start"], v1[1]["start"]), (v1[2]["start"], v1[2]["start"] + v1[2]["duration"])]
        mid = next(i for i in tracks["video"][0]["items"] if i["id"] == v1[1]["id"])
        assert mid["grade"] is not None and mid["grade"]["values"]["exposure"] == 1.5     # the scene's grade, its own now
        assert cl.post(f"{base}/grade/own", json={"clip": v1[1]["id"]}).status_code == 422   # under no scene grade any more
