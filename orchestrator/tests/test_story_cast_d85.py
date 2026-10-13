"""17 (D85) · SY1 Cast: profiles with versions (a version's reference set is an album group), locking (the group refuses every change, 423),
copying a version, the coverage presets and the Expand plan (one T2I per cell with the hero as reference 1), the Expand route on the fake
engine (one batch, the results on the candidates page with their cell, suite story), curation, profile mentions and the capabilities."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.groups import GroupLocked, GroupStore  # noqa: E402
from loom2.mentions import resolve_mentions  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import T2I, Mention  # noqa: E402
from loom2.story import PRESETS, StoryStore, cell_sentence, expand_spec, plan_expand, preset_cells  # noqa: E402

from test_groups_d34 import _png, _setup  # noqa: E402
from test_lifecycle import Rig  # noqa: E402

KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max > 1)


def _story(tmp_path: Path):
    ws, cat, groups, _ = _setup(tmp_path)
    ids = [cat.ingest_file(_png(tmp_path / f"c{i}.png")).id for i in range(4)]
    return ws, cat, groups, ids, StoryStore(ws)


# ---- profiles and versions ------------------------------------------------------------------------------------------------------
def test_profile_create_patch_copy_lock_delete(tmp_path: Path):
    ws, cat, groups, ids, st = _story(tmp_path)
    p = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0], stub="Mara, a wiry courier in a grey coat")
    v = p.version()
    assert p.current == "v1" and v.state == "open" and v.hero_asset_id == ids[0] and v.stub.startswith("Mara, a wiry")
    g = groups.groups[v.group_id]
    assert g.name == "Mara · v1" and g.cover_id == ids[0] and groups.parent[("asset", ids[0])] == g.id     # the hero moved onto the page as its cover
    assert [x.id for x in st.profiles()] == [p.id] and st.profile(p.id) == p
    with pytest.raises(ValueError):
        st.create_profile("  ", "prop", groups)
    # patch: the stub and the name; a stale revision is refused
    p2 = st.patch_profile(p.id, {"revision": p.revision, "name": "Mara Vey", "versions": [{"id": "v1", "stub": "Mara Vey, a courier"}]})
    assert p2.revision == p.revision + 1 and p2.name == "Mara Vey" and p2.version().stub == "Mara Vey, a courier"
    from loom2.story import StaleProfile
    with pytest.raises(StaleProfile):
        st.patch_profile(p.id, {"revision": p.revision, "name": "x"})
    with pytest.raises(ValueError):
        st.patch_profile(p.id, {"revision": p2.revision, "current": "v9"})
    # more refs, then a copy: the group is duplicated (its assets copied — one page per asset), the copy is current and open
    groups.move([("asset", ids[1])], v.group_id)
    p3 = st.new_version(p.id, groups)
    v2 = p3.version()
    assert p3.current == "v2" and v2.derived_from == "v1" and v2.state == "open" and v2.stub == "Mara Vey, a courier"
    g2 = groups.groups[v2.group_id]
    assert g2.name == "Mara Vey · v2" and len([i for i in g2.items if i.kind == "asset"]) == 2 and g2.id != g.id
    assert v2.hero_asset_id == g2.cover_id and cat.get(v2.hero_asset_id).duplicate_of == ids[0]
    assert len([i for i in groups.groups[g.id].items if i.kind == "asset"]) == 2                              # v1 keeps its own
    # lock v1: the group refuses every change; the profile's fields for v1 are read-only; mentions still resolve (below)
    p4 = st.lock_version(p.id, "v1", groups)
    assert p4.version("v1").state == "final" and p4.version("v1").locked_at and groups.groups[g.id].locked
    for call in (lambda: groups.move([("asset", ids[2])], g.id), lambda: groups.move([("asset", ids[0])], None), lambda: groups.update(g.id, name="x"),
                 lambda: groups.layout(g.id, []), lambda: groups.delete(g.id), lambda: groups.group_items(g.id, [("asset", ids[0])], "sub")):
        with pytest.raises(GroupLocked):
            call()
    with pytest.raises(ValueError, match="locked"):
        st.patch_profile(p.id, {"revision": p4.revision, "versions": [{"id": "v1", "stub": "changed"}]})
    assert st.lock_version(p.id, "v1", groups).revision == p4.revision                                         # locking twice is a no-op
    assert groups.move([("asset", ids[2])], g2.id)                                                            # v2's page is still open
    # delete: the record goes, the groups stay and are unlocked again
    assert st.delete_profile(p.id, groups) and st.profile(p.id) is None and not st.delete_profile(p.id, groups)
    assert not groups.groups[g.id].locked and g.id in groups.groups and g2.id in groups.groups


def test_lock_needs_a_hero(tmp_path: Path):
    ws, cat, groups, ids, st = _story(tmp_path)
    p = st.create_profile("Tavern", "place", groups)
    with pytest.raises(ValueError, match="hero"):
        st.lock_version(p.id, "v1", groups)
    with pytest.raises(ValueError, match="hero"):
        plan_expand(p, p.version(), "npc", "full", width=960, height=544, group_id="g")


# ---- coverage and the Expand plan --------------------------------------------------------------------------------------------------
def test_presets_and_cells():
    counts = {k: len(preset_cells(k)) for k in PRESETS}
    assert counts["comprehensive"] >= 80 and 35 <= counts["full"] <= 45 and 25 <= counts["portrait"] <= 32 and 38 <= counts["fullbody"] <= 48 and 15 <= counts["npc"] <= 22
    cells = preset_cells("npc")
    assert cells[0] == {"shot": "close-up", "angle": "front", "expression": "neutral", "take": 1}
    assert all({"shot", "angle", "expression", "take"} <= set(c) for c in cells)
    assert cell_sentence({"shot": "waist-up", "angle": "three-quarter left", "expression": "neutral"}) == "a waist-up medium shot, a three-quarter view from the left, neutral expression"
    with pytest.raises(ValueError, match="unknown preset"):
        preset_cells("nope")
    assert expand_spec("full") is not None and expand_spec("full").recipes.t2i


def test_plan_expand_one_recipe_per_cell(tmp_path: Path):
    ws, cat, groups, ids, st = _story(tmp_path)
    p = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0], stub="Mara, a wiry courier.")
    planned = plan_expand(p, p.version(), "npc", "full", seeds_per_cell=2, width=960, height=544, style_id="sty_a", tier="draft", group_id="grp_c")
    assert len(planned) == 2 * len(preset_cells("npc"))
    recipe, origin = planned[0]
    assert recipe["kind"] == "t2i" and recipe["model_id"] == expand_spec("full").id and recipe["prompt_mode"] == "text"
    assert recipe["prompt_text"] == "Mara, a wiry courier. a close-up of the face, seen from the front, neutral expression."
    assert recipe["refs"] == [{"asset_id": ids[0], "note": "Mara"}] and recipe["style_id"] == "sty_a" and recipe["width"] == 960
    assert origin == {"suite": "story", "surface": "expand", "ref": p.id, "payload": {"version": "v1", "cell": {"shot": "close-up", "angle": "front", "expression": "neutral", "take": 1}, "group_id": "grp_c", "preset": "npc"}}
    assert planned[1][1]["payload"]["cell"]["take"] == 2                                                        # the second seed of the same cell
    takes = [o["payload"]["cell"]["take"] for _, o in planned[:4]]
    assert takes == [1, 2, 1, 2]
    st.lock_version(p.id, "v1", groups)
    with pytest.raises(ValueError, match="locked"):
        plan_expand(st.profile(p.id), st.profile(p.id).version(), "npc", "full", width=960, height=544, group_id="g")


# ---- mentions of profiles ------------------------------------------------------------------------------------------------------
def test_profile_mentions_resolve_to_the_version_group_with_the_stub(tmp_path: Path):
    ws, cat, groups, ids, st = _story(tmp_path)
    p = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0], stub="Mara, a wiry courier in a grey coat.")
    groups.move([("asset", ids[1])], p.version().group_id)
    r = T2I(model_id=KLEIN, prompt_text="@Mara at the gate", mentions=[Mention(profile_id=p.id, name="Mara")])
    out = resolve_mentions(r, groups, cat, 4, st)
    m = out.mentions[0]
    assert (m.group_id, m.profile_id, m.version, m.name) == (p.version().group_id, p.id, "v1", "Mara") and m.revision is not None
    assert [x.asset_id for x in out.refs] == [ids[0], ids[1]] and out.refs[0].note == "Mara, a wiry courier in a grey coat"   # the hero first, the stub on the note
    assert resolve_mentions(out, groups, cat, 4, st) is out                                                    # stamped: not resolved again
    # a new version: an unpinned mention follows the current one; a pinned one stays on v1 (locked or not)
    st.new_version(p.id, groups)
    v2 = st.profile(p.id).version()
    cur = resolve_mentions(T2I(model_id=KLEIN, mentions=[Mention(profile_id=p.id)]), groups, cat, 4, st).mentions[0]
    assert cur.version == "v2" and cur.group_id == v2.group_id and cur.name == "Mara"
    pin = resolve_mentions(T2I(model_id=KLEIN, mentions=[Mention(profile_id=p.id, version="v1")]), groups, cat, 4, st).mentions[0]
    assert pin.version == "v1" and pin.group_id == p.version("v1").group_id
    with pytest.raises(ValueError, match="does not exist"):
        resolve_mentions(T2I(model_id=KLEIN, mentions=[Mention(profile_id="prf_nope")]), groups, cat, 4, st)
    with pytest.raises(ValueError, match="no version"):
        resolve_mentions(T2I(model_id=KLEIN, mentions=[Mention(profile_id=p.id, version="v9")]), groups, cat, 4, st)
    with pytest.raises(ValueError, match="group or a profile"):
        resolve_mentions(T2I(model_id=KLEIN, mentions=[Mention()]), groups, cat, 4, st)
    with pytest.raises(ValueError, match="open project"):
        resolve_mentions(T2I(model_id=KLEIN, mentions=[Mention(profile_id=p.id)]), groups, cat, 4, None)
    # a stub equal to the name adds nothing to the note
    q = st.create_profile("Lantern", "prop", groups, hero_asset_id=ids[2])
    assert resolve_mentions(T2I(model_id=KLEIN, mentions=[Mention(profile_id=q.id)]), groups, cat, 4, st).refs[0].note == "Lantern"


# ---- the routes: create from a hero, curate, lock → 423 on the album, expand on the fake engine, capabilities ---------------------
def test_routes_profiles_and_curate(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.get("/story/profiles").status_code == 409
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ids = [svc.catalogue.ingest_file(_png(tmp_path / f"r{i}.png")).id for i in range(4)]
        assert cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": "ast_nope"}).status_code == 422
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": ids[0], "stub": "Mara, a courier"}).json()
        gid = p["versions"][0]["group_id"]
        assert cl.get("/story/profiles").json()["items"][0]["id"] == p["id"] and cl.get(f"/story/profiles/{p['id']}").json()["name"] == "Mara"
        assert cl.get(f"/groups/{gid}").json()["group"]["cover_id"] == ids[0]
        # curate: keep moves onto the reference page with state keep; reject marks and leaves
        c = cl.post(f"/story/profiles/{p['id']}/versions/v1/curate", json={"asset_ids": [ids[1], ids[2]], "verdict": "keep"}).json()
        assert c["kept"] == [ids[1], ids[2]] and svc.catalogue.get(ids[1]).state == "keep" and svc.groups.parent[("asset", ids[2])] == gid
        c = cl.post(f"/story/profiles/{p['id']}/versions/v1/curate", json={"asset_ids": [ids[3]], "verdict": "reject"}).json()
        assert c["rejected"] == [ids[3]] and svc.catalogue.get(ids[3]).state == "reject" and ("asset", ids[3]) not in svc.groups.parent
        # patch with the revision; stale → 409; a bad current → 422
        p = cl.get(f"/story/profiles/{p['id']}").json()
        r = cl.patch(f"/story/profiles/{p['id']}", json={"revision": p["revision"], "versions": [{"id": "v1", "stub": "Mara Vey, a courier"}]})
        assert r.status_code == 200 and r.json()["versions"][0]["stub"] == "Mara Vey, a courier"
        assert cl.patch(f"/story/profiles/{p['id']}", json={"revision": p["revision"], "name": "x"}).status_code == 409
        assert cl.patch(f"/story/profiles/{p['id']}", json={"revision": p["revision"] + 1, "current": "v7"}).status_code == 422
        # lock: the album's routes answer 423 on the reference page; curate is refused; the preview still resolves @Mara
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/lock")
        assert r.status_code == 200 and r.json()["versions"][0]["state"] == "final"
        assert cl.post("/groups/move", json={"items": [{"kind": "asset", "id": ids[1]}], "to": None}).status_code == 423
        assert cl.patch(f"/groups/{gid}", json={"name": "renamed"}).status_code == 423
        assert cl.delete(f"/groups/{gid}").status_code == 423
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/curate", json={"asset_ids": [ids[3]], "verdict": "keep"}).status_code == 423
        pv = cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": KLEIN, "prompt_mode": "text", "prompt_text": "@Mara at the gate",
                                                           "mentions": [{"profile_id": p["id"], "name": "Mara"}]}}).json()
        assert pv["mentions"][0]["profile_id"] == p["id"] and pv["mentions"][0]["version"] == "v1" and pv["mentions"][0]["group_id"] == gid
        assert "Image 1 shows Mara, Mara Vey, a courier." in pv["serialized_prompt"] or "Image 1 shows Mara" in pv["serialized_prompt"]
        assert cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": KLEIN, "mentions": [{"profile_id": "prf_nope"}]}}).status_code == 422
        # a new version copies the page; the old stays locked
        r = cl.post(f"/story/profiles/{p['id']}/versions")
        assert r.status_code == 200 and r.json()["current"] == "v2" and r.json()["versions"][1]["derived_from"] == "v1"
        g2 = r.json()["versions"][1]["group_id"]
        assert cl.get(f"/groups/{g2}").json()["group"]["locked"] is False and len(cl.get(f"/groups/{g2}").json()["assets"]) == 3
        # expand on a locked version is refused; capabilities say the model and the presets
        assert cl.post(f"/story/profiles/{p['id']}/expand", json={"version": "v1", "preset": "npc"}).status_code == 422
        assert cl.post(f"/story/profiles/{p['id']}/expand", json={"preset": "nope"}).status_code == 422
        caps = cl.get("/capabilities").json()["story"]
        assert caps["model_id"] == expand_spec("full").id and caps["presets"]["npc"]["cells"] == len(preset_cells("npc")) and "close-up" in caps["coverage"]["shots"]
        # delete: the groups stay, unlocked
        assert cl.delete(f"/story/profiles/{p['id']}").json()["deleted"] == p["id"]
        assert cl.get(f"/story/profiles/{p['id']}").status_code == 404 and cl.get(f"/groups/{gid}").json()["group"]["locked"] is False


async def test_expand_runs_one_job_per_cell_and_places_the_candidates(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        st = StoryStore(rig.ws)
        hero = rig.catalogue.ingest_file(_png(tmp_path / "hero.png")).id
        p = st.create_profile("Mara", "character", rig.queue.groups, hero_asset_id=hero, stub="Mara, a courier")
        rig.queue.load()
        await rig.queue.start()
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and sp.inputs.refs_max and rig.roster.resolve(i).path)   # weights in the fake tree
        cand = rig.queue.groups.create("Mara · v1 · candidates")
        planned = plan_expand(p, p.version(), "npc", "full", width=64, height=64, group_id=cand.id)[:3]
        from loom2.fsio import new_id
        from loom2.origin import JobOrigin
        batch = new_id("bat")
        jobs = [rig.queue.submit({**r, "model_id": mid, "seeds": [7]}, origin=JobOrigin.model_validate(o), batch_id=batch)[0] for r, o in planned]
        assert {j.batch_id for j in jobs} == {batch} and all(j.recipe["refs"][0]["asset_id"] == hero for j in jobs)
        for j in jobs:
            done = await rig.wait(j.id)
            assert done.status == "done", done.error
            a = rig.catalogue.get(done.result["asset_ids"][0])
            assert a.suite == "story" and a.params["coverage_cell"] == j.origin.payload["cell"] and a.parents == [hero]
            assert rig.queue.groups.parent[("asset", a.id)] == cand.id                                        # placed on the candidates page
    finally:
        await rig.close()
