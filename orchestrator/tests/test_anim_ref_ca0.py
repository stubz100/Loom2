"""CA0 (proto01_animate 01 step 2, §10): a Cast version's animation reference — made with the clay-reference model from the version's
sheet and references (an @mention pinned to the version), 16:9 at the Draft height, a neutral A-pose on a plain ground (a prop alone in a
three-quarter view; a back view for characters only); the results land on the candidates page and the first becomes the reference while
the version has none; the author's pick replaces it, on a final version too."""
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
from loom2.story import StoryStore, expand_spec, plan_anim_ref  # noqa: E402

from test_groups_d34 import _png, _setup  # noqa: E402
from test_lifecycle import Rig  # noqa: E402


def test_the_plan(tmp_path: Path):
    ws, cat, groups, _ = _setup(tmp_path)
    st = StoryStore(ws)
    hero = cat.ingest_file(_png(tmp_path / "h.png")).id
    p = st.create_profile("Mara", "character", groups, hero_asset_id=hero, appearance="Mara, a wiry courier", outfit="a yellow oilskin",
                          colours=[{"hex": "#F2A93B", "object": "oilskin"}])
    planned = plan_anim_ref(p, p.version(), "front", "full", width=1280, height=720, count=2, group_id="grp_c")
    assert len(planned) == 2 and [r["seeds"] for r, _ in planned] == [[0], [1]]
    r, o = planned[0]
    assert r["model_id"] == expand_spec("full").id and (r["width"], r["height"]) == (1280, 720)
    assert r["prompt_text"].startswith("Mara, a wiry courier") and "#F2A93B oilskin" in r["prompt_text"]          # the sheet, colours bound
    assert "A-pose" in r["prompt_text"] and "facing the camera" in r["prompt_text"] and "plain light grey" in r["prompt_text"]
    assert r["mentions"] == [{"group_id": "", "name": "Mara", "profile_id": p.id, "version": "v1"}]                 # the references, pinned
    assert o == {"suite": "story", "surface": "anim_ref", "ref": p.id, "payload": {"version": "v1", "side": "front", "group_id": "grp_c"}}
    back = plan_anim_ref(p, p.version(), "back", "full", width=1280, height=720, count=9, group_id="g")
    assert len(back) == 4 and "from directly behind" in back[0][0]["prompt_text"]
    prop = st.create_profile("Compass", "prop", groups, appearance="a brass compass")
    assert "three-quarter view" in plan_anim_ref(prop, prop.version(), "front", "full", width=1280, height=720, count=1, group_id="g")[0][0]["prompt_text"]
    with pytest.raises(ValueError, match="only a character has a back view"):
        plan_anim_ref(prop, prop.version(), "back", "full", width=1280, height=720, count=1, group_id="g")
    place = st.create_profile("Quay", "place", groups)
    with pytest.raises(ValueError, match="a place has no animation reference"):
        plan_anim_ref(place, place.version(), "front", "full", width=1280, height=720, count=1, group_id="g")


@pytest.mark.asyncio
async def test_the_first_result_becomes_the_reference(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        st = StoryStore(rig.ws)
        hero = rig.catalogue.ingest_file(_png(tmp_path / "hero.png")).id
        p = st.create_profile("Mara", "character", groups, hero_asset_id=hero, appearance="Mara, a courier")
        p, gid, _ = st.ensure_candidates(p.id, "v1", groups)
        rig.queue.load()
        await rig.queue.start()
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and sp.inputs.refs_max and rig.roster.resolve(i).path)
        planned = plan_anim_ref(p, p.version(), "front", "full", width=64, height=64, count=2, group_id=gid)
        jobs = [rig.queue.submit({**r, "model_id": mid}, origin=JobOrigin.model_validate(o))[0] for r, o in planned]
        made = []
        for j in jobs:
            done = await rig.wait(j.id)
            assert done.status == "done", done.error
            made.append(done.result["asset_ids"][0])
        v = st.profile(p.id).version("v1")
        assert v.anim_ref_asset_id == made[0] and v.anim_ref_back_asset_id is None                     # the first; the second does not replace it
        assert all(groups.parent[("asset", a)] == gid for a in made)                                  # every result on the candidates page
        assert hero in rig.catalogue.get(made[0]).parents                                              # lineage: the version's references
        # the author's pick replaces it, a final version too; None clears it
        assert st.lock_version(p.id, "v1", groups).version("v1").state == "final"
        assert st.set_anim_ref(p.id, "v1", "front", made[1]).version("v1").anim_ref_asset_id == made[1]
        assert st.set_anim_ref(p.id, "v1", "back", made[0]).version("v1").anim_ref_back_asset_id == made[0]
        assert st.set_anim_ref(p.id, "v1", "front", None).version("v1").anim_ref_asset_id is None
    finally:
        await rig.close()


def test_the_routes(tmp_path: Path):
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        hero = app.state.services.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": hero, "appearance": "Mara, a courier"}).json()
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "front", "count": 2, "stage": True})
        assert r.status_code == 200, r.text
        out = r.json()
        assert len(out["job_ids"]) == 2 and out["group_id"] and out["model_id"] == expand_spec("full").id
        jobs = {j["id"]: j for j in cl.get("/jobs").json()["items"]}
        j = jobs[out["job_ids"][0]]
        assert j["status"] == "staged" and (j["recipe"]["width"], j["recipe"]["height"]) == (1280, 720) and j["origin"]["surface"] == "anim_ref"
        assert cl.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "front", "asset_id": hero}).json()["versions"][0]["anim_ref_asset_id"] == hero
        assert cl.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "front", "asset_id": "ast_nope"}).status_code == 422
        assert cl.put(f"/story/profiles/{p['id']}/versions/v9/anim-ref", json={"side": "front", "asset_id": None}).status_code == 404
        place = cl.post("/story/profiles", json={"name": "Quay", "cls": "place"}).json()
        assert cl.post(f"/story/profiles/{place['id']}/versions/v1/anim-ref", json={}).status_code == 422
