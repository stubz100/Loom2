"""U4 (D157, proto01_UI2 06 §2.3): an older project brought into "a shot is a camera of its own on its scene's stage", once.

- a Shot without a stage gets one for its scene (a scene of its own when it is in none); a Shot in a scene that has a stage gets a new
  camera on it; a final version keeps its record;
- shots that look through one camera: the first keeps it, each other one's open versions get a copy with its keys;
- the cameras are added at the stage's revision — nothing made through the other cameras goes stale;
- it runs once, and a stageless shot made after it (the old UI's *New shot…*) is left as it was made;
- a bench or the line-up is not a shot's scene.
"""
from pathlib import Path

import pytest

from loom2.fsio import atomic_write_json, read_json
from loom2.stages import StageStore
from loom2.story import StoryStore
from loom2.workspace import Workspace


def _old(ws: Workspace) -> None:
    """The book as a project before U4 left it (schema 2)."""
    p = ws.story_dir / "flow" / "scenes.json"
    atomic_write_json(p, {**(read_json(p) if p.is_file() else {"scenes": [], "revision": 0}), "schema_version": 2})


def test_stageless_shots_get_a_camera_on_their_scenes_stage(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    lone = st.create_node("shot", "Arrival")                                        # no scene, no stage (the old Image to video route)
    quay = stages.create("Quay")
    wide = st.create_node("shot", "Wide")
    scn = st.create_scene("At the quay", [wide.id])
    st.set_source(wide.shot_id, "v1", quay.id, quay.cameras[0].id, quay.revision)   # the scene owns the quay
    close = st.create_node("shot", "Close")
    st._join([close.id], scn.id)                                                     # in the scene, no stage of its own
    done = st.create_node("shot", "Done")
    rec = read_json(st.node_path(done.id))
    rec["shot"]["versions"][0]["state"] = "final"
    atomic_write_json(st.node_path(done.id), rec)
    rev = stages.get(quay.id).revision
    _old(ws)
    again = StoryStore(ws)
    assert again.migrated == ["U4: 2 shots without a stage got a camera of their own on their scene's stage",
                              "U4: 1 final shot without a stage kept its record — a new version can be blocked on one"]
    v = again.shot(lone.shot_id).version()
    own = stages.get(v.stage_id)
    assert own.name == "Arrival" and v.camera_id == own.cameras[0].id and v.stage_revision == own.revision
    node = again.flow_node(lone.id)
    assert node.scene_id and next(s for s in again.scene_book().scenes if s.id == node.scene_id).stage_id == own.id   # a scene of its own, owning it
    c = again.shot(close.shot_id).version()
    after = stages.get(quay.id)
    assert c.stage_id == quay.id and [x.name for x in after.cameras] == ["Camera 1", "Camera 2"] and c.camera_id == after.cameras[1].id
    assert after.revision == rev                                                     # at its revision: the wide shot's work stays current
    assert again.shot(done.shot_id).version().stage_id is None                       # a final version is a fixed record
    assert StoryStore(ws).migrated == []                                             # once


def test_shots_sharing_a_camera_get_their_own(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    stg = stages.create("Pier")
    cam = stg.cameras[0]
    stg = stages.put(stg.id, {"revision": stg.revision, "keyframes": {"camera": {cam.id: [{"frame": 0, "pos": [0, 1.6, 4]}, {"frame": 48, "pos": [0, 1.6, 2]}]}}})
    a = st.create_node("shot", "Wide", 0, 0)                                          # the first in the Flow keeps the camera
    st.set_source(a.shot_id, "v1", stg.id, cam.id, stg.revision)
    b = st.create_node("shot", "Again", 300, 0)
    rec = read_json(st.node_path(b.id))                                             # before U2 a second shot could take the same camera
    rec["shot"]["versions"][0].update({"stage_id": stg.id, "camera_id": cam.id, "stage_revision": stg.revision})
    atomic_write_json(st.node_path(b.id), rec)
    _old(ws)
    again = StoryStore(ws)
    assert again.migrated == ["U4: 1 shot sharing a camera got its own (a copy, keys and all)"]
    va, vb = again.shot(a.shot_id).version(), again.shot(b.shot_id).version()
    after = stages.get(stg.id)
    assert va.camera_id == cam.id and vb.camera_id != cam.id and [c.name for c in after.cameras] == ["Camera 1", "Camera 1 2"]
    assert after.keyframes["camera"][vb.camera_id] == after.keyframes["camera"][cam.id]   # the keys with it
    assert after.revision == stg.revision and vb.stage_revision == stg.revision      # nothing goes stale


def test_once_and_a_stageless_shot_made_later_is_left(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    StoryStore(ws)                                                                    # a new project: marked at once
    assert read_json(ws.story_dir / "flow" / "scenes.json")["schema_version"] == 3
    st = StoryStore(ws)
    n = st.create_node("shot", "Later")
    assert StoryStore(ws).migrated == [] and StoryStore(ws).shot(n.shot_id).version().stage_id is None


def test_a_bench_is_no_scene(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    bench = stages.create("Mara's bench")
    stages.save(bench.model_copy(update={"purpose": "bench"}))
    n = st.create_node("shot", "Wide")
    with pytest.raises(ValueError, match="bench"):
        st.set_source(n.shot_id, "v1", bench.id, bench.cameras[0].id, bench.revision)


def test_the_header_changes_a_shots_scene(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    a = st.make_shot("Wide")
    b = st.create_node("shot", "Close")
    va = st.shot(a.shot_id).version()
    same = st.rescene(b.shot_id, "v1", "same", like=a.id).version()                 # Same scene as the shot before: a copy of its camera
    assert same.stage_id == va.stage_id and same.camera_id != va.camera_id and st.flow_node(b.id).scene_id == st.flow_node(a.id).scene_id
    new = st.rescene(b.shot_id, "v1", "new").version()                              # New scene…: a stage and a scene of its own
    scn = st.flow_node(b.id).scene_id
    assert stages.get(new.stage_id).name == "Close" and scn != st.flow_node(a.id).scene_id
    assert next(s for s in st.scene_book().scenes if s.id == scn).stage_id == new.stage_id
    with pytest.raises(ValueError, match="shot before"):
        st.rescene(a.shot_id, "v1", "same", like=None)
