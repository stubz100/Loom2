"""D93 phase A · Cast ↔ subject made real: (A1) a casting run from Generate lands in the version's candidates (the page made on demand, the
origin's `group_id`); (A2) "Add to character ▸" — an image as the hero / into the reference set / as a candidate, moved from Unprocessed
or the version's candidates, copied from any other page, refused by a final version; (A3) the prompt binds each linked subject to its
own reference images per family (Klein prose, dev JSON), the slots split fairly within the model's limit and what was left out said;
(A9) a new profile's stub starts empty."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine.graphs import effective_params, ref_span, serialize_prompt  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.mentions import resolve_mentions  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import T2I, Mention, RefImage  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_groups_d34 import _png, _setup  # noqa: E402
from test_lifecycle import Rig  # noqa: E402

# D65: no model ids — the families by what their specs say
KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max == 4 and s.inputs.bind_refs)
DEV = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and s.sampling.json_prompt and s.inputs.refs_max >= 6 and s.inputs.bind_refs)


def _cast(tmp_path: Path, n: int = 8):
    ws, cat, groups, _ = _setup(tmp_path)
    ids = [cat.ingest_file(_png(tmp_path / f"c{i}.png")).id for i in range(n)]
    st = StoryStore(ws)
    mara = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0], stub="Mara, a wiry courier in a grey coat")
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[3], stub="a lighthouse keeper in a yellow oilskin")
    groups.move([("asset", ids[1]), ("asset", ids[2])], mara.version().group_id)
    groups.move([("asset", ids[4]), ("asset", ids[5])], ines.version().group_id)
    return ws, cat, groups, ids, st, mara, ines


def _two_subjects(model: str, mara, ines, **kw) -> T2I:
    tree = {"scene": "a harbour at dusk", "subjects": [{"description": "Mara, a wiry courier in a grey coat", "position": "left"},
                                                       {"description": "a lighthouse keeper in a yellow oilskin", "position": "right"}]}
    return T2I(model_id=model, prompt_mode="tree", prompt_json=tree, mentions=[Mention(profile_id=mara.id, name="Mara", subject=0),
                                                                               Mention(profile_id=ines.id, name="Ines", subject=1)], **kw)


# ---- A3 · the binding ----------------------------------------------------------------------------------------------------------------
def test_ref_span_words():
    assert ref_span([2]) == "reference image 2" and ref_span([1, 2, 3]) == "reference images 1–3" and ref_span([1, 3]) == "reference images 1, 3"


def test_klein_prose_binds_each_subject_to_its_contiguous_range_within_the_limit(tmp_path: Path):
    _, cat, groups, ids, st, mara, ines = _cast(tmp_path)
    out = resolve_mentions(_two_subjects(KLEIN, mara, ines), groups, cat, 4, st)
    # four slots split fairly (two each, by turns), then each subject's together: Mara 1–2, Ines 3–4; one of each set left out
    assert [r.asset_id for r in out.refs] == [ids[0], ids[1], ids[3], ids[4]]
    assert [(m.subject, m.skipped) for m in out.mentions] == [(0, 1), (1, 1)]
    spec = registry.SPECS[KLEIN]
    text, mode = serialize_prompt(out, spec)
    assert mode == "prose"
    assert "Mara (reference images 1–2), a wiry courier in a grey coat" in text                         # the name leads: the range after it
    assert "Ines (reference images 3–4), a lighthouse keeper in a yellow oilskin" in text               # a description without the name gets it
    assert "Image 1 shows" not in text                                                                 # the bound images are said by their subject
    ep = effective_params(out)
    assert ep["bind_refs"] is True and [(b["subject"], b["name"], b["refs"], b["skipped"]) for b in ep["bindings"]] == [(0, "Mara", [1, 2], 1), (1, "Ines", [3, 4], 1)]
    assert ep["ref_notes"] == 0 and ep["serialized_prompt"] == text                                    # T8: the preview's text is what is sent
    # off (the recipe's choice): the D73 sentences per image, the subjects as written
    off, _ = serialize_prompt(out.model_copy(update={"bind_refs": False}), spec)
    assert "(reference images" not in off and "Image 1 shows Mara, a wiry courier in a grey coat." in off and "Image 3 shows Ines, a lighthouse keeper" in off


def test_dev_json_puts_the_range_into_the_subject_object_and_keeps_other_notes(tmp_path: Path):
    _, cat, groups, ids, st, mara, ines = _cast(tmp_path)
    r = _two_subjects(DEV, mara, ines, refs=[RefImage(asset_id=ids[7], note="the lamp")])
    out = resolve_mentions(r, groups, cat, registry.SPECS[DEV].inputs.refs_max, st)
    assert [x.asset_id for x in out.refs] == [ids[7], ids[0], ids[1], ids[2], ids[3], ids[4], ids[5]]   # the explicit one first, then each set whole
    text, mode = serialize_prompt(out, registry.SPECS[DEV])
    tree = json.loads(text)
    assert mode == "json" and tree["subjects"][0]["reference"] == "reference images 2–4" and tree["subjects"][1]["reference"] == "reference images 5–7"
    assert tree["subjects"][0]["description"] == "Mara, a wiry courier in a grey coat"                  # the JSON family reads the field, not a rewritten text
    assert tree["references"] == [{"index": 1, "note": "the lamp"}]                                     # only the unbound reference keeps its note


def test_no_binding_without_a_linked_subject_or_in_text_mode(tmp_path: Path):
    _, cat, groups, ids, st, mara, _ = _cast(tmp_path)
    text_mode = resolve_mentions(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="@Mara at the gate", mentions=[Mention(profile_id=mara.id, name="Mara")]), groups, cat, 4, st)
    assert effective_params(text_mode)["bindings"] == [] and "Image 1 shows Mara" in serialize_prompt(text_mode)[0]
    unlinked = resolve_mentions(T2I(model_id=KLEIN, prompt_mode="tree", prompt_json={"subjects": [{"description": "a dog"}]}, mentions=[Mention(profile_id=mara.id, name="Mara")]),
                                groups, cat, 4, st)
    assert effective_params(unlinked)["bindings"] == []


def test_a_cut_at_the_limit_counts_as_skipped(tmp_path: Path):
    """References over the model's limit (more explicit ones than room) are cut from the end — a subject's images among them are said."""
    _, cat, groups, ids, st, mara, ines = _cast(tmp_path)
    out = resolve_mentions(_two_subjects(KLEIN, mara, ines), groups, cat, 10, st)                     # resolved for a bigger model …
    ep = effective_params(out)                                                                         # … then run on Klein's 4
    assert ep["refs_dropped"] == 2 and [(b["refs"], b["skipped"]) for b in ep["bindings"]] == [([1, 2, 3], 0), ([4], 2)]


# ---- A9 · the empty stub -------------------------------------------------------------------------------------------------------------
def test_a_new_profile_starts_with_an_empty_stub(tmp_path: Path):
    _, cat, groups, ids, st, _, _ = _cast(tmp_path)
    p = st.create_profile("char01", "character", groups)
    assert p.version().stub == ""
    out = resolve_mentions(T2I(model_id=KLEIN, prompt_mode="text", prompt_text="@char01", mentions=[Mention(profile_id=p.id, name="char01")]), groups, cat, 4, st)
    assert out.refs == [] and out.mentions[0].asset_ids == []                                          # no look yet: nothing reaches the model


# ---- A2 · Add to character ▸ (the store) ------------------------------------------------------------------------------------------------
def test_add_moves_from_unprocessed_and_candidates_copies_from_elsewhere(tmp_path: Path):
    ws, cat, groups, ids, st, mara, ines = _cast(tmp_path)
    loose = ids[6]                                                                                     # Unprocessed
    r = st.add_assets(mara.id, None, [loose], "reference", groups, cat)
    assert r["moved"] == [loose] and groups.parent[("asset", loose)] == mara.version().group_id and cat.get(loose).state == "keep"
    # from another profile's set: copied, the original stays on Ines's page
    r = st.add_assets(mara.id, None, [ids[4]], "reference", groups, cat)
    dup = r["copied"][ids[4]]
    assert r["asset_ids"] == [dup] and groups.parent[("asset", ids[4])] == ines.version().group_id and groups.parent[("asset", dup)] == mara.version().group_id
    # as a candidate: the page is made on first use
    r = st.add_assets(mara.id, None, [ids[7]], "candidate", groups, cat)
    cand = st.profile(mara.id).version().candidates_group_id
    assert r["made_page"] and r["group_id"] == cand and groups.parent[("asset", ids[7])] == cand
    # the hero from the candidates page: moved onto the reference set as its cover
    r = st.add_assets(mara.id, None, [ids[7]], "hero", groups, cat)
    v = st.profile(mara.id).version()
    assert r["moved"] == [ids[7]] and v.hero_asset_id == ids[7] and groups.groups[v.group_id].cover_id == ids[7] and groups.parent[("asset", ids[7])] == v.group_id
    assert st.profile(mara.id).revision == mara.revision + 2                                          # the candidates page and the hero
    # already there: nothing moves
    assert st.add_assets(mara.id, None, [ids[1]], "reference", groups, cat)["already"] == [ids[1]]


# ---- the routes: A1's candidates page, A2's add with its refusals ----------------------------------------------------------------------
def test_routes_candidates_and_add(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ids = [svc.catalogue.ingest_file(_png(tmp_path / f"r{i}.png")).id for i in range(4)]
        p = cl.post("/story/profiles", json={"name": "char01", "cls": "character"}).json()
        assert p["versions"][0]["appearance"] == "" and p["versions"][0]["candidates_group_id"] is None      # A9: empty; no candidates page yet
        # A1: the casting run's page, made once
        r = cl.post(f"/story/profiles/{p['id']}/candidates", json={})
        cand = r.json()["versions"][0]["candidates_group_id"]
        assert r.status_code == 200 and cand and cl.get(f"/groups/{cand}").status_code == 200
        assert cl.post(f"/story/profiles/{p['id']}/candidates", json={"version": "v1"}).json()["versions"][0]["candidates_group_id"] == cand
        assert cl.post("/story/profiles/prf_nope/candidates", json={}).status_code == 404
        svc.groups.move([("asset", ids[0]), ("asset", ids[1])], cand)                                  # as the finisher places a casting run's results
        # A2: one of them becomes the hero (moved onto the reference set as its cover)
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/add", json={"asset_ids": [ids[0]], "role": "hero"})
        assert r.status_code == 200 and r.json()["moved"] == [ids[0]] and r.json()["profile"]["versions"][0]["hero_asset_id"] == ids[0]
        gid = r.json()["group_id"]
        assert gid == p["versions"][0]["group_id"] and cl.get(f"/groups/{gid}").json()["group"]["cover_id"] == ids[0]
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/add", json={"asset_ids": [ids[1], ids[2]], "role": "hero"}).status_code == 422   # one hero
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/add", json={"asset_ids": ["ast_nope"], "role": "reference"}).status_code == 422
        assert cl.post(f"/story/profiles/{p['id']}/versions/v9/add", json={"asset_ids": [ids[1]], "role": "reference"}).status_code == 404
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/add", json={"asset_ids": [ids[1], ids[2]], "role": "reference"}).json()
        assert sorted(r["moved"]) == sorted([ids[1], ids[2]])
        # the preview now brings the look: three references (hero first)
        pv = cl.post("/recipes/preview", json={"recipe": {"kind": "t2i", "model_id": KLEIN, "prompt_mode": "tree", "prompt_json": {"subjects": [{"description": "char01"}]},
                                                           "mentions": [{"profile_id": p["id"], "name": "char01", "subject": 0}]}}).json()
        assert [r_["asset_id"] for r_ in pv["ref_list"]][0] == ids[0] and pv["bindings"][0]["refs"] == [1, 2, 3] and pv["bindings"][0]["span"] == "reference images 1–3"
        assert "char01 (reference images 1–3)" in pv["serialized_prompt"] and pv["mentions"][0]["subject"] == 0
        # a final version refuses, with the reason
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/lock").status_code == 200
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/add", json={"asset_ids": [ids[3]], "role": "reference"})
        assert r.status_code == 423 and "final" in r.json()["detail"]
        assert cl.post(f"/story/profiles/{p['id']}/candidates", json={}).status_code == 423


# ---- A1 · a casting run's results land in the candidates (fake engine) -------------------------------------------------------------------
async def test_a_casting_run_lands_in_the_candidates(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        st = StoryStore(rig.ws)
        p = st.create_profile("char01", "character", rig.queue.groups)
        p, cand, _ = st.ensure_candidates(p.id, None, rig.queue.groups)
        rig.queue.load()
        await rig.queue.start()
        mid = next(i for i, sp in registry.SPECS.items() if sp.recipes.t2i and sp.inputs.refs_max and rig.roster.resolve(i).path)
        from loom2.origin import JobOrigin
        origin = JobOrigin(suite="generate", surface="cast", ref=p.id, payload={"version": "v1", "group_id": cand, "profile_id": p.id})
        jobs = rig.queue.submit({"kind": "t2i", "model_id": mid, "prompt_mode": "tree", "prompt_json": {"subjects": [{"description": "char01, a red-haired diver"}]},
                                 "mentions": [{"profile_id": p.id, "name": "char01", "subject": 0}], "width": 64, "height": 64, "seeds": [1, 2]}, origin=origin)
        assert len(jobs) == 2
        for j in jobs:
            done = await rig.wait(j.id)
            assert done.status == "done", done.error
            a = rig.catalogue.get(done.result["asset_ids"][0])
            assert rig.queue.groups.parent[("asset", a.id)] == cand and a.suite == "generate"            # in the version's candidates, made in Generate
    finally:
        await rig.close()
