"""D73 (ArtCraft P12): reference notes serialised per model family, no silent truncation of references, and @mentions of album groups
that resolve to references (cover first, then page order, taking turns, capped by the model) with their provenance stamped into the
recipe the asset's manifest keeps."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loom2.api import create_app
from loom2.config import AppState
from loom2.engine import graphs
from loom2.groups import GroupStore
from loom2.mentions import candidates, resolve_mentions
from loom2.models import registry
from loom2.recipes import T2I, Mention, RefImage

from test_generate_m3 import _tree
from test_groups_d34 import _png, _setup
from test_lifecycle import Rig

# by trait, not by id (D65: no model ids in code): a JSON-prompted model and a prose one that both take references
DEV = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and s.sampling.json_prompt and s.inputs.refs_max > 1)
KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max > 1)


def _spec(mid: str):
    s = registry.get(mid)
    assert s is not None, mid
    return s


# ---- notes ------------------------------------------------------------------------------------------------------------------------
def test_notes_go_into_the_prompt_per_model_family():
    refs = [RefImage(asset_id="a", note="the hero, red coat"), RefImage(asset_id="b"), RefImage(asset_id="c", note="  the tavern.  ")]
    tree = {"scene": "a street at night"}
    dev, mode = graphs.serialize_prompt(T2I(model_id=DEV, prompt_mode="tree", prompt_json=tree, refs=refs), _spec(DEV))
    assert mode == "json" and dev.endswith(',"references":[{"index":1,"note":"the hero, red coat"},{"index":3,"note":"the tavern."}]}')
    prose, mode = graphs.serialize_prompt(T2I(model_id=KLEIN, prompt_mode="tree", prompt_json=tree, refs=refs), _spec(KLEIN))
    assert mode == "prose" and prose == "scene: a street at night. Image 1 shows the hero, red coat. Image 3 shows the tavern."
    text, mode = graphs.serialize_prompt(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="she walks in", refs=refs), _spec(KLEIN))
    assert mode == "text" and text == "she walks in. Image 1 shows the hero, red coat. Image 3 shows the tavern."
    plain, _ = graphs.serialize_prompt(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="she walks in", refs=[RefImage(asset_id="a")]), _spec(KLEIN))
    assert plain == "she walks in"                                                    # no notes, no change
    ep = graphs.effective_params(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="x", refs=refs))
    assert ep["ref_notes"] == 2


def test_notes_count_only_the_references_the_model_takes():
    spec = _spec(KLEIN)
    n = spec.inputs.refs_max
    refs = [RefImage(asset_id=f"a{i}", note=f"thing {i + 1}") for i in range(n + 2)]
    text, _ = graphs.serialize_prompt(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="x", refs=refs), spec)
    assert f"Image {n} shows thing {n}." in text and f"Image {n + 1}" not in text


def test_mention_tokens_read_as_names():
    r = T2I(model_id=KLEIN, prompt_mode="tree", prompt_json={"scene": "@Old tavern at dusk", "subjects": [{"description": "@hero walks in"}]},
            prompt_text="@hero", mentions=[Mention(group_id="g1", name="hero"), Mention(group_id="g2", name="Old tavern")])
    text, _ = graphs.serialize_prompt(r, _spec(KLEIN))
    assert "@" not in text and "Old tavern at dusk" in text and "hero walks in" in text


# ---- no silent truncation ---------------------------------------------------------------------------------------------------------
def test_references_over_the_limit_are_reported_dropped_or_refused(tmp_path: Path, object_info: dict):
    roster = _tree(tmp_path)
    mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and not sp.sampling.json_prompt and sp.inputs.refs_max and roster.resolve(i).path)
    n = _spec(mid).inputs.refs_max
    refs = [{"asset_id": f"ast_{i}"} for i in range(n + 2)]
    ep = graphs.effective_params(T2I(model_id=mid, prompt_text="x", refs=refs))
    assert (ep["refs"], ep["max_refs"], ep["refs_dropped"]) == (n, n, 2)
    with pytest.raises(graphs.FieldError) as e:
        graphs.effective_params(T2I(model_id=mid, prompt_text="x", refs=refs, size_policy="error"))
    assert e.value.detail()["field"] == "refs" and e.value.detail()["value"] == n + 2 and e.value.detail()["allowed"] == [n]
    info = copy.deepcopy(object_info)
    names = {f"ast_{i}": f"r{i}.png" for i in range(n + 2)}
    info["LoadImage"]["input"]["required"]["image"][0] += list(names.values())
    c = graphs.compile_recipe(T2I(model_id=mid, prompt_text="x", refs=refs), roster, info, 1, "p", ref_files=names)
    assert [x["class_type"] for x in c.graph.values()].count("ReferenceLatent") == n and c.summary["refs_dropped"] == 2


# ---- the resolver ------------------------------------------------------------------------------------------------------------------
def _hero_and_tavern(tmp_path: Path):
    ws, cat, st, ids = _setup(tmp_path, 7)
    hero, tavern = st.create("hero"), st.create("tavern")
    st.move([("asset", i) for i in ids[:4]], hero.id)
    st.move([("asset", i) for i in ids[4:6]], tavern.id)
    # hero's page, top to bottom, left to right: ids[1] (0,0), ids[0] (300,0), ids[2] (0,200), ids[3] (300,200); the cover is ids[3]
    pos = {ids[0]: (300, 0), ids[1]: (0, 0), ids[2]: (0, 200), ids[3]: (300, 200)}
    st.layout(hero.id, [{"kind": "asset", "id": i, "x": x, "y": y} for i, (x, y) in pos.items()])
    st.update(hero.id, cover_id=ids[3])
    return ws, cat, st, ids, st.groups[hero.id], st.groups[tavern.id]


def test_candidates_cover_first_then_page_order_skipping_the_trash(tmp_path: Path):
    _, cat, st, ids, hero, _ = _hero_and_tavern(tmp_path)
    assert candidates(st, cat, hero.id) == [ids[3], ids[1], ids[0], ids[2]]
    cat.trash([ids[1]])
    assert candidates(st, cat, hero.id) == [ids[3], ids[0], ids[2]]
    with pytest.raises(ValueError):
        candidates(st, cat, "grp_missing")


def test_mentions_take_turns_within_the_room_left_and_are_stamped(tmp_path: Path):
    _, cat, st, ids, hero, tavern = _hero_and_tavern(tmp_path)
    r = T2I(model_id=KLEIN, prompt_text="@hero walks into @tavern", refs=[RefImage(asset_id=ids[6], note="the lamp")],
            mentions=[Mention(group_id=hero.id, name="hero"), Mention(group_id=tavern.id, name="tavern")])
    out = resolve_mentions(r, st, cat, 4)
    # one explicit reference, then three turns: hero's cover, tavern's first, hero's next — capped at the model's 4; D93 (A3): then each
    # mention's images together (hero's two, then tavern's), the explicit one in front
    assert [(x.asset_id, x.note, x.mention) for x in out.refs] == [(ids[6], "the lamp", None), (ids[3], "hero", hero.id),
                                                                   (ids[1], "hero", hero.id), (ids[4], "tavern", tavern.id)]
    assert out.mentions[0].skipped == 2                                                  # D93: hero's other two did not fit
    assert [m.model_dump(exclude={"profile_id", "version", "lora", "lora_available", "subject", "skipped", "shot", "composed", "scene", "held_by", "figure"}) for m in out.mentions] == [{"group_id": hero.id, "name": "hero", "revision": hero.revision, "asset_ids": [ids[3], ids[1]]},
                                                      {"group_id": tavern.id, "name": "tavern", "revision": tavern.revision, "asset_ids": [ids[4]]}]   # D85: profile fields (D92: and the subject link) stay None for a group
    assert resolve_mentions(out, st, cat, 4) is out                                    # stamped: not resolved again (a re-run uses the same images)
    assert resolve_mentions(r, st, cat, 1).refs == r.refs                              # no room left: a mention never pushes a reference out
    dup = T2I(model_id=KLEIN, refs=[RefImage(asset_id=ids[3])], mentions=[Mention(group_id=hero.id)])
    assert [x.asset_id for x in resolve_mentions(dup, st, cat, 10).refs] == [ids[3], ids[1], ids[0], ids[2]]   # deduplicated, name from the group
    assert resolve_mentions(dup, st, cat, 10).mentions[0].name == "hero"
    empty = st.create("empty")
    assert resolve_mentions(T2I(mentions=[Mention(group_id=empty.id)]), st, cat, 4).refs == []
    with pytest.raises(ValueError):
        resolve_mentions(T2I(mentions=[Mention(group_id="grp_nope")]), st, cat, 4)
    with pytest.raises(ValueError):
        resolve_mentions(T2I(mentions=[Mention(group_id=hero.id)]), None, None, 4)        # no project


# ---- the API: preview shows them, submit refuses over the cap on request -------------------------------------------------------------
def test_preview_shows_the_mentions_references_and_the_drop(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ids = [svc.catalogue.ingest_file(_png(tmp_path / f"{i}.png")).id for i in range(3)]
        g = svc.groups.create("hero")
        svc.groups.move([("asset", i) for i in ids], g.id)
        mid = cl.get("/capabilities").json()["defaults"]["t2i"]
        cap = cl.get("/capabilities").json()["models"][mid]["max_refs"]
        p = cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "@hero at the door",
                                                          "mentions": [{"group_id": g.id, "name": "hero"}]}}).json()
        took = min(3, cap)
        assert p["refs"] == took and p["refs_dropped"] == 0 and len(p["ref_list"]) == took
        assert all(r["mention"] == g.id and r["note"] == "hero" for r in p["ref_list"])
        assert p["mentions"][0]["group_id"] == g.id and p["mentions"][0]["revision"] == svc.groups.groups[g.id].revision
        assert "@" not in p["serialized_prompt"] and "Image 1 shows hero." in p["serialized_prompt"] or p["prompt_mode"] == "json"
        over = {"kind": "t2i", "model_id": mid, "prompt_text": "x", "refs": [{"asset_id": ids[0]}] * 0 + [{"asset_id": f"ast_{i}"} for i in range(cap + 1)]}
        assert cl.post("/recipes/preview", json={"recipe": over}).json()["refs_dropped"] == 1
        for r in (cl.post("/jobs", json={"recipe": {**over, "size_policy": "error"}}), cl.post("/recipes/preview", json={"recipe": {**over, "size_policy": "error"}})):
            assert r.status_code == 422 and r.json()["detail"]["field"] == "refs" and r.json()["detail"]["allowed"] == [cap]
        assert cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": mid, "mentions": [{"group_id": "grp_nope"}]}}).status_code == 422


# ---- provenance: the asset's manifest keeps the stamped mentions ------------------------------------------------------------------
async def test_the_asset_records_its_mentions_at_their_revision(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        ids = [rig.catalogue.ingest_file(_png(tmp_path / f"m{i}.png")).id for i in range(2)]
        g = rig.queue.groups.create("hero")
        rig.queue.groups.move([("asset", i) for i in ids], g.id)
        rev = rig.queue.groups.groups[g.id].revision
        rig.queue.load()
        await rig.queue.start()
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and sp.inputs.refs_max and rig.roster.resolve(i).path)   # weights in the fake tree
        job = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": "@hero", "seeds": [3], "width": 64, "height": 64,
                                "mentions": [{"group_id": g.id, "name": "hero"}]})[0]
        assert job.recipe["mentions"][0]["revision"] == rev and job.recipe["refs"]            # stamped before the job record was written
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        a = rig.catalogue.get(done.result["asset_ids"][0])
        m = a.params["recipe"]["mentions"][0]
        assert (m["group_id"], m["revision"]) == (g.id, rev) and set(m["asset_ids"]) <= set(ids) and m["asset_ids"]
        assert set(a.parents) == set(m["asset_ids"])                                           # lineage: the images it was made from
    finally:
        await rig.close()
