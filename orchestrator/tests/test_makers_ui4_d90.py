"""D90 (02 §5, §4.2) · wave UI4, makers in context: a job made *for* a shot version (`origin.surface == "for_shot"`, payload {shot_id,
version}) is checked at submit (the shot and an open version) and its results land as takes of that version — a frame from Generate,
a clip from Animate, the first one filling an empty slot; a Flow node carries a board (an album group) the route checks."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.origin import JobOrigin  # noqa: E402
from loom2.story import FOR_SHOT, StoryStore, check_for_shot, for_shot_target  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_groups_d34 import _png  # noqa: E402
from test_lifecycle import Rig  # noqa: E402

KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max > 1)
WAN = next(s.id for s in registry.video_specs() if s.graph == "wan22")


def _origin(sid: str, vid: str = "v1", suite: str = "generate") -> JobOrigin:
    return JobOrigin(suite=suite, surface=FOR_SHOT, ref=None, payload={"shot_id": sid, "version": vid})   # type: ignore[arg-type]


def test_the_target_and_the_submit_check(tmp_path: Path):
    assert for_shot_target({"shot_id": "sht_1", "version": "v2"}) == ("sht_1", "v2")
    assert for_shot_target(None) is None and for_shot_target({"shot_id": "sht_1"}) is None and for_shot_target({"shot_id": "", "version": "v1"}) is None
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    s = st.create_shot("Gate")
    assert check_for_shot(st, {"shot_id": s.id, "version": "v1"}).id == s.id
    with pytest.raises(ValueError, match="names the shot and its version"):
        check_for_shot(st, {"version": "v1"})
    with pytest.raises(ValueError, match="does not exist"):
        check_for_shot(st, {"shot_id": "sht_gone", "version": "v1"})
    with pytest.raises(ValueError, match="has no version v9"):
        check_for_shot(st, {"shot_id": s.id, "version": "v9"})
    v = s.version()
    st.save_shot(s.model_copy(update={"versions": [v.model_copy(update={"state": "final"})]}))
    with pytest.raises(ValueError, match="is final"):
        check_for_shot(st, {"shot_id": s.id, "version": "v1"})


@pytest.mark.asyncio
async def test_frames_and_clips_made_for_a_shot_land_as_its_takes(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        _pin_review().full_roster(tmp_path / "models")
        rig.roster.scan()
        rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        rig.queue.load()
        await rig.queue.start()
        st = StoryStore(rig.ws)
        shot = st.create_shot("Gate")
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and rig.roster.resolve(i).path)   # weights in the fake tree
        jobs = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "a gate at dawn", "width": 64, "height": 64, "seeds": [3, 4]},
                                origin=_origin(shot.id))
        made = []
        for j in jobs:
            done = await rig.wait(j.id)
            assert done.status == "done", done.error
            made += done.result["asset_ids"]
        v = st.shot(shot.id).version("v1")
        assert [(t.kind, t.id) for t in v.takes] == [("image", a) for a in made]
        assert v.frame_asset_id == made[0]                                                   # the first fills the empty frame; later ones are takes only
        assert rig.catalogue.get(made[0]).origin.surface == FOR_SHOT                         # still a Catalogue asset with its origin
        # Animate for the shot: the clip is a take, and the version's clip while it has none
        start = rig.catalogue.ingest_file(_png(tmp_path / "start.png"), move=False, suite="animate")
        job = rig.queue.submit({"kind": "i2v", "model_id": WAN, "start_asset": start.id, "prompt_text": "the gate opens", "frames": 9, "fps": 16, "width": 832, "height": 480},
                               origin=_origin(shot.id, suite="animate"))[0]
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        v = st.shot(shot.id).version("v1")
        assert v.takes[-1].kind == "clip" and v.takes[-1].id == done.result["clip_id"] and v.clip_id == done.result["clip_id"]
        # a version finalized while its job ran: the job still succeeds, the result stays in the Catalogue only
        s = st.shot(shot.id)
        st.save_shot(s.model_copy(update={"versions": [s.version().model_copy(update={"state": "final"})]}))
        job = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "late", "width": 64, "height": 64, "seeds": [5]}, origin=_origin(shot.id))[0]
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        assert done.result["asset_ids"][0] not in [t.id for t in st.shot(shot.id).version().takes]
    finally:
        await rig.close()


def test_routes_check_the_shot_and_the_board(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        sh = cl.post("/story/shots", json={"name": "Gate"}).json()
        recipe = {"kind": "t2i", "model_id": KLEIN, "prompt_mode": "text", "prompt_text": "a gate", "width": 512, "height": 512, "seeds": [1]}
        origin = {"suite": "generate", "surface": FOR_SHOT, "ref": None, "payload": {"shot_id": sh["id"], "version": "v1"}}
        r = cl.post("/jobs", json={"recipe": recipe, "stage": True, "origin": origin})
        assert r.status_code == 200, r.text
        assert r.json()["jobs"][0]["origin"]["payload"] == {"shot_id": sh["id"], "version": "v1"}
        for payload, why in (({"shot_id": "sht_gone", "version": "v1"}, "does not exist"), ({"shot_id": sh["id"]}, "names the shot"), ({"shot_id": sh["id"], "version": "v7"}, "no version v7")):
            r = cl.post("/jobs", json={"recipe": recipe, "stage": True, "origin": {**origin, "payload": payload}})
            assert r.status_code == 422 and why in r.json()["detail"], r.text
        # a board on a node: an album group, shown back on the node; an unknown id is refused; null removes it
        g = svc.groups.create("Gate · board")
        n = cl.post("/story/flow/nodes", json={"type": "shot", "title": "Gate"}).json()
        assert n["board_group_id"] is None
        r = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "board_group_id": "grp_nope"})
        assert r.status_code == 422 and "not a group" in r.json()["detail"]
        n = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "board_group_id": g.id}).json()
        assert n["board_group_id"] == g.id
        assert next(x for x in cl.get("/story/flow").json()["nodes"] if x["id"] == n["id"])["board_group_id"] == g.id
        n = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "title": "Gate 2"}).json()                 # a patch without it keeps it
        assert n["board_group_id"] == g.id
        assert cl.delete(f"/groups/{g.id}").status_code == 200                                                                  # the group goes: the node keeps the id
        n = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "title": "Gate 3", "board_group_id": g.id})        # a save that sends it back passes
        assert n.status_code == 200, n.text
        n = n.json()
        n = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "board_group_id": None}).json()
        assert n["board_group_id"] is None
