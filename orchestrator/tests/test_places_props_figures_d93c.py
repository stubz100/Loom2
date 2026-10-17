"""D93 phase C · places, props and figures: (C6) a Cast place linked to the Tree's scene composes the scene from its sheet (+ this shot's line)
and binds its images to it; a Cast prop held by a subject card is said "holding <its clause>" and bound to that subject, per family (Klein
prose, dev JSON); a place or a prop wears no outfit; the images sit subject by subject with the held prop after its holder, the place after
the subjects; a stamped recipe is never composed again. (C7) a Flow node names where it happens (`place_id`, a Cast place — 422 otherwise),
old node files read. (C8) a Stage figure is bound to a character (`profile_id`, `version` on the object; old stages read, only a figure
binds); a StageShot's figures bring their references within the method's room, left to right, each figure's sheet and range in the prompt
("figure 1 is Mara (reference images 2–3), …"), the preview lists which images are a figure's, the graph takes them."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine import graphs  # noqa: E402
from loom2.engine.graphs import effective_params, serialize_prompt, stage_bindings, stage_prompt  # noqa: E402
from loom2.engine.pipeline import plan  # noqa: E402
from loom2.mentions import resolve_figures, resolve_mentions  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import T2I, Mention, RefImage, StageShot, SubjectShot, stage_spec  # noqa: E402
from loom2.stages import Stage, check as check_stage  # noqa: E402
from loom2.story import FlowNode, ProfileVersion, StoryStore, compose_sheet  # noqa: E402

from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_groups_d34 import _png, _setup  # noqa: E402

KLEIN = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and not s.sampling.json_prompt and s.inputs.refs_max == 4 and s.inputs.bind_refs)
DEV = next(i for i, s in registry.SPECS.items() if s.recipes.t2i and s.sampling.json_prompt and s.inputs.refs_max >= 6 and s.inputs.bind_refs)
CLAY = stage_spec("clay")
PASSES = {"clay": "ast_clay", "pose": "ast_pose"}


def _world(tmp_path: Path, n: int = 12):
    """Mara and Ines (characters, three images each), the harbour (a place, two) and the compass (a prop, two)."""
    ws, cat, groups, _ = _setup(tmp_path)
    ids = [cat.ingest_file(_png(tmp_path / f"w{i}.png")).id for i in range(n)]
    st = StoryStore(ws)
    mara = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0], appearance="Mara, a wiry courier, cropped black hair")
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[3], appearance="a lighthouse keeper with curly red hair")
    harbour = st.create_profile("Harbour", "place", groups, hero_asset_id=ids[6], appearance="a stone quay at dusk, fishing boats", outfit="a coat it cannot wear")
    compass = st.create_profile("Compass", "prop", groups, hero_asset_id=ids[8], appearance="a brass compass with a cracked glass")
    groups.move([("asset", ids[1]), ("asset", ids[2])], mara.version().group_id)
    groups.move([("asset", ids[4]), ("asset", ids[5])], ines.version().group_id)
    groups.move([("asset", ids[7])], harbour.version().group_id)
    groups.move([("asset", ids[9])], compass.version().group_id)
    return ws, cat, groups, ids, st, mara, ines, harbour, compass


# ---- C6 · places and props in the Tree ------------------------------------------------------------------------------------------------
def test_a_place_or_a_prop_wears_nothing():
    v = ProfileVersion(id="v1", group_id="g", appearance="a stone quay", outfit="a red coat", marks="a broken lamp post")
    assert compose_sheet(v, None, "Harbour", "place") == "a stone quay, a broken lamp post"
    assert compose_sheet(v, SubjectShot(outfit="rain gear", note="in the rain"), "Harbour", "place") == "a stone quay, a broken lamp post, in the rain"
    assert compose_sheet(v, None, "Mara") == "a stone quay, wearing a red coat, a broken lamp post"        # a character still does


def test_the_place_is_the_scene_and_binds_its_images_klein(tmp_path: Path):
    _, cat, groups, ids, st, mara, ines, harbour, _ = _world(tmp_path)
    tree = {"scene": "", "subjects": [{"description": "", "position": "left"}]}
    r = T2I(model_id=KLEIN, prompt_mode="tree", prompt_json=tree, mentions=[Mention(profile_id=mara.id, name="Mara", subject=0),
                                                                          Mention(profile_id=harbour.id, name="Harbour", scene=True, shot=SubjectShot(note="rain on the stones"))])
    out = resolve_mentions(r, groups, cat, 4, st)
    assert out.prompt_json["scene"] == "a stone quay at dusk, fishing boats, rain on the stones"                 # the sheet + this shot's line, no outfit
    assert out.mentions[1].composed == out.prompt_json["scene"] and out.mentions[1].scene is True
    assert [x.mention for x in out.refs] == [mara.version().group_id] * 2 + [harbour.version().group_id] * 2  # the subject first, then the place
    text, mode = serialize_prompt(out, registry.SPECS[KLEIN])
    assert mode == "prose" and "scene: Harbour (reference images 3–4), a stone quay at dusk, fishing boats, rain on the stones" in text
    assert "Mara (reference images 1–2), a wiry courier" in text and "Image " not in text
    ep = effective_params(out)
    assert [(b["role"], b["subject"], b["refs"]) for b in ep["bindings"]] == [("subject", 0, [1, 2]), ("scene", None, [3, 4])] and ep["serialized_prompt"] == text


def test_dev_json_leads_the_scene_with_its_range(tmp_path: Path):
    _, cat, groups, ids, st, mara, _, harbour, _ = _world(tmp_path)
    r = T2I(model_id=DEV, prompt_mode="tree", prompt_json={"subjects": [{"description": ""}]},
            mentions=[Mention(profile_id=harbour.id, name="Harbour", scene=True), Mention(profile_id=mara.id, name="Mara", subject=0)])
    out = resolve_mentions(r, groups, cat, registry.SPECS[DEV].inputs.refs_max, st)
    tree = json.loads(serialize_prompt(out, registry.SPECS[DEV])[0])
    assert tree["subjects"][0]["reference"] == "reference images 1–3"                                        # the subject's set first, though written second
    assert tree["scene"] == "Harbour (reference images 4–5), a stone quay at dusk, fishing boats"


def test_a_held_prop_is_said_and_bound_to_its_holder_in_both_families(tmp_path: Path):
    _, cat, groups, ids, st, mara, ines, _, compass = _world(tmp_path)
    tree = {"subjects": [{"description": "", "position": "left"}, {"description": "", "position": "right"}]}
    ms = [Mention(profile_id=mara.id, name="Mara", subject=0), Mention(profile_id=ines.id, name="Ines", subject=1), Mention(profile_id=compass.id, name="Compass", held_by=1)]
    out = resolve_mentions(T2I(model_id=KLEIN, prompt_mode="tree", prompt_json=tree, mentions=ms), groups, cat, 4, st)
    # four slots by turns (Mara, Ines, Compass, Mara), then subject by subject with the prop after its holder: Mara 1–2, Ines 3, Compass 4
    assert [x.mention for x in out.refs] == [mara.version().group_id] * 2 + [ines.version().group_id, compass.version().group_id]
    assert out.prompt_json["subjects"][1]["holding"] == "a brass compass with a cracked glass" and out.mentions[2].composed == "a brass compass with a cracked glass"
    text, _ = serialize_prompt(out, registry.SPECS[KLEIN])
    assert "Ines (reference image 3), a lighthouse keeper with curly red hair, holding Compass (reference image 4), a brass compass with a cracked glass" in text
    ep = effective_params(out)
    assert [(b["role"], b["subject"], b["refs"]) for b in ep["bindings"]] == [("subject", 0, [1, 2]), ("subject", 1, [3]), ("held", 1, [4])]
    off, _ = serialize_prompt(out.model_copy(update={"bind_refs": False}), registry.SPECS[KLEIN])           # unbound: the words, and D73's sentence per image
    assert "curly red hair, holding a brass compass with a cracked glass" in off and "Image 4 shows Compass, a brass compass" in off
    dev = resolve_mentions(T2I(model_id=DEV, prompt_mode="tree", prompt_json=tree, mentions=ms), groups, cat, registry.SPECS[DEV].inputs.refs_max, st)
    j = json.loads(serialize_prompt(dev, registry.SPECS[DEV])[0])
    assert j["subjects"][1]["holding"] == {"description": "a brass compass with a cracked glass", "reference": "reference images 7–8"}


def test_a_free_subject_can_hold_a_prop_and_a_stamped_recipe_is_not_composed_again(tmp_path: Path):
    _, cat, groups, ids, st, _, _, _, compass = _world(tmp_path)
    r = T2I(model_id=KLEIN, prompt_mode="tree", prompt_json={"subjects": [{"description": "an old sailor"}]}, mentions=[Mention(profile_id=compass.id, name="Compass", held_by=0)])
    out = resolve_mentions(r, groups, cat, 4, st)
    text, _ = serialize_prompt(out)
    assert "an old sailor, holding Compass (reference images 1–2), a brass compass with a cracked glass" in text
    again = resolve_mentions(out, groups, cat, 4, st)                                                        # stamped: unchanged
    assert again == out and serialize_prompt(again)[0] == text
    nobody = resolve_mentions(r.model_copy(update={"mentions": [Mention(profile_id=compass.id, name="Compass", held_by=3)]}), groups, cat, 4, st)
    assert "holding" not in json.dumps(nobody.prompt_json) and effective_params(nobody)["bindings"] == []    # no such holder: only its images (D73's note)


# ---- C7 · where a Flow node happens ------------------------------------------------------------------------------------------------------
def test_a_node_names_a_place_old_node_files_read(tmp_path: Path):
    old = {"schema_version": 1, "id": "node_1", "type": "dialogue", "title": "At the gate", "lines": [], "options": [], "cond": None, "set": [], "target": None,
           "text": "", "shot_id": None, "shot_version": None, "board_group_id": None, "colour": None, "revision": 2, "created_at": "x", "updated_at": "x"}
    assert FlowNode.model_validate(old).place_id is None
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        place = cl.post("/story/profiles", json={"name": "Harbour", "cls": "place"}).json()
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        n = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "At the gate"}).json()
        r = cl.patch(f"/story/flow/nodes/{n['id']}", json={"place_id": place["id"]})
        assert r.status_code == 200 and r.json()["place_id"] == place["id"]
        assert cl.patch(f"/story/flow/nodes/{n['id']}", json={"place_id": mara["id"]}).status_code == 422          # a character is not a place
        assert cl.patch(f"/story/flow/nodes/{n['id']}", json={"place_id": "prf_nope"}).status_code == 422
        assert cl.patch(f"/story/flow/nodes/{n['id']}", json={"place_id": None}).json()["place_id"] is None


# ---- C8 · Stage figures bound to characters ---------------------------------------------------------------------------------------------
def _stage(**obj) -> dict:
    return {"id": "stg_1", "objects": [{"id": "fig_a", "kind": "mannequin", "name": "Figure 1", **obj}], "cameras": [{"id": "cam_1"}], "active_camera": "cam_1"}


def test_a_figure_binds_a_character_old_stages_read():
    st = Stage.model_validate(_stage())
    assert st.objects[0].profile_id is None and st.objects[0].version is None                                # a stage from before C8
    check_stage(Stage.model_validate(_stage(profile_id="prf_1", version="v2")))
    bad = Stage.model_validate({**_stage(), "objects": [{"id": "crate", "kind": "prop", "name": "Crate", "profile_id": "prf_1"}]})
    with pytest.raises(ValueError, match="only a figure"):
        check_stage(bad)


def _figures(mara, ines, **kw) -> StageShot:
    return StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, prompt_text="a harbour at dusk",
                     mentions=[Mention(profile_id=mara.id, figure="fig_left"), Mention(profile_id=ines.id, figure="fig_right")], **kw)


def test_figures_bring_their_references_within_the_method_room_left_to_right(tmp_path: Path):
    _, cat, groups, ids, st, mara, ines, _, _ = _world(tmp_path)
    room = CLAY.inputs.refs_max - 1                                                                           # the clay pass is image 1
    out = resolve_figures(_figures(mara, ines), groups, cat, room, st)
    mg, ig = mara.version().group_id, ines.version().group_id
    assert [x.mention for x in out.refs] == [mg, mg, ig] and [(m.name, len(m.asset_ids), m.skipped) for m in out.mentions] == [("Mara", 2, 1), ("Ines", 1, 2)]
    assert out.mentions[0].composed == "Mara, a wiry courier, cropped black hair" and out.mentions[1].composed == "a lighthouse keeper with curly red hair"
    text = stage_prompt(out)
    assert text.startswith(graphs.STAGE_CLAY_LEAD)
    assert ("From left to right in image 1: figure 1 is Mara (reference images 2–3), a wiry courier, cropped black hair; "
            "figure 2 is Ines (reference image 4), a lighthouse keeper with curly red hair.") in text
    assert "Image 2 shows" not in text and text.endswith("a harbour at dusk")
    figs = stage_bindings(out, CLAY)
    assert [(b["figure"], b["object_id"], b["refs"], b["skipped"]) for b in figs] == [(1, "fig_left", [2, 3], 1), (2, "fig_right", [4], 2)]
    off = stage_prompt(out.model_copy(update={"bind_refs": False}))                                          # unbound: D73's sentences, the figures by their words
    assert "figure 1 is Mara, a wiry courier, cropped black hair; figure 2 is Ines, a lighthouse keeper" in off and "(reference image" not in off
    assert "Image 2 shows Mara, a wiry courier" in off and "Image 4 shows Ines, a lighthouse keeper" in off
    assert resolve_figures(out, groups, cat, room, st) == out                                                 # stamped: a re-run uses the same images


def test_the_deck_comes_first_and_refcontrol_takes_one(tmp_path: Path):
    _, cat, groups, ids, st, mara, ines, _, _ = _world(tmp_path)
    deck = _figures(mara, ines, refs=[RefImage(asset_id=ids[11], note="the lamp")])
    out = resolve_figures(deck, groups, cat, CLAY.inputs.refs_max - 1, st)
    assert [x.asset_id for x in out.refs][:1] == [ids[11]] and len(out.refs) == 3
    assert [b["refs"] for b in stage_bindings(out, CLAY)] == [[3], [4]] and "Image 2 shows the lamp." in stage_prompt(out)
    exact = resolve_figures(_figures(mara, ines, method="refcontrol"), groups, cat, 1, st)
    assert [x.mention for x in exact.refs] == [mara.version().group_id]                                     # the first figure's image is image 2
    assert "figure 1 is Mara (reference image 2)" in stage_prompt(exact) and "figure 2 is Ines, a lighthouse keeper" in stage_prompt(exact)
    with pytest.raises(ValueError, match="same character"):
        resolve_figures(StageShot(stage_id="s", camera_id="c", passes=PASSES, mentions=[Mention(profile_id=mara.id, figure="a"), Mention(profile_id=mara.id, figure="b")]),
                        groups, cat, 3, st)
    with pytest.raises(ValueError, match="names a stage figure"):
        resolve_figures(StageShot(stage_id="s", camera_id="c", passes=PASSES, mentions=[Mention(profile_id=mara.id)]), groups, cat, 3, st)


def test_the_plan_lists_the_figures_slots_and_the_graph_takes_them(tmp_path: Path, object_info: dict):
    _, cat, groups, ids, st, mara, ines, _, _ = _world(tmp_path)
    out = resolve_figures(_figures(mara, ines), groups, cat, CLAY.inputs.refs_max - 1, st)
    p = plan(out, "full")
    assert p.params["bind_refs"] is True and [f["figure"] for f in p.params["figures"]] == [1, 2]
    assert [(x["image"], x["figure"]) for x in p.params["ref_list"]] == [(2, 1), (3, 1), (4, 2)] and p.params["prompt"] == stage_prompt(out)
    roster = _pin_review().full_roster(tmp_path)
    files = {r.asset_id: "alley-rain_s20261004.png" for r in out.refs}
    c = graphs.compile_recipe(out, roster, object_info, 7, "loom2/shot", ref_files=files, inputs={"clay": "alley-rain_s20261004.png"})
    assert c.problems == [] and [n["class_type"] for n in c.graph.values()].count("ReferenceLatent") == 4 and c.serialized_prompt == p.params["prompt"]


def test_the_preview_route_resolves_bound_figures(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        hero = svc.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": hero, "appearance": "a wiry courier"}).json()
        s = cl.post("/stages", json={"name": "Quay"}).json()
        doc = {**s, "objects": [{"id": "fig_a", "kind": "mannequin", "name": "Figure 1", "profile_id": mara["id"]}]}
        r = cl.put(f"/stages/{s['id']}", json=doc)
        assert r.status_code == 200 and r.json()["objects"][0]["profile_id"] == mara["id"]
        recipe = {"kind": "stage_shot", "stage_id": s["id"], "camera_id": "cam", "passes": {"clay": "pending"}, "mentions": [{"profile_id": mara["id"], "figure": "fig_a"}]}
        pv = cl.post("/recipes/preview", json={"recipe": recipe}).json()
        assert pv["params"]["figures"][0]["refs"] == [2] and pv["params"]["ref_list"] == [{"image": 2, "asset_id": hero, "figure": 1}]
        assert "figure 1 is Mara (reference image 2), a wiry courier" in pv["params"]["prompt"]
