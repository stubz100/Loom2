"""D186: the model is picked where the picture is made — the server side.

- a Stage method's models (`stage_models`): the measured default first, then every FLUX.2-family model that takes references (clay) or
  implements the pose LoRA (refcontrol), per variant; `StageShot.model_id` is honoured when it is one of them and refused by name otherwise;
- a guest model's stage graph: FLUX.2 dev runs the clay method at its edit settings (the Turbo LoRA, 8 steps, FluxGuidance 4.0, CFG 1, no
  negative) with image 1 and the deck as reference latents; Klein's measured graph is unchanged; the plan's estimate says what is measured;
- /capabilities lists the models per method (the Still's card), the default first;
- the set's painting model (`set_model`): the set's card when it runs the job, else the kind's default;
- the reference model (`expand_spec`): the Make column's card when it is a FLUX.2-family model with reference slots, else the clay model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs  # noqa: E402
from loom2.engine.pipeline import plan  # noqa: E402
from loom2.place_sets import set_model  # noqa: E402
from loom2.recipes import RefImage, StageShot, parse_recipe, stage_model_id, stage_models, warm_group  # noqa: E402
from loom2.stages import PlaceSet  # noqa: E402
from loom2.story import StoryStore, expand_spec, plan_anim_ref  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_groups_d34 import _png, _setup  # noqa: E402

PASSES = {"clay": "ast_clay", "pose": "ast_pose", "depth": "ast_depth"}
INPUTS = {"clay": "alley-rain_s20261004.png", "pose": "alley-rain_s20261004.png"}
REFS = {"ast_hero": "alley-rain_s20261004.png", "ast_tavern": "alley-rain_s20261004.png"}
DEV = "flux2-dev-fp8mixed"


def test_the_methods_models_and_the_pick():
    clay = [s.id for s in stage_models("clay")]
    assert clay[0] == "klein-9b" and DEV in clay and "klein-base-9b" in clay and "zimage-bf16" not in clay     # the measured default first; the FLUX.2 family only
    assert [s.id for s in stage_models("refcontrol")] == ["klein-base-9b"]                                     # the pose LoRA's base alone
    assert [s.id for s in stage_models("clay", "open")][0] == "klein-4b" and DEV not in [s.id for s in stage_models("clay", "open")]   # D26: dev is flux-nc
    r = StageShot(stage_id="s", camera_id="c", passes=PASSES)
    assert r.model_id is None and stage_model_id(r) == "klein-9b" and r.model == "klein-9b"                   # None: the measured default
    picked = StageShot(stage_id="s", camera_id="c", passes=PASSES, model_id=DEV)
    assert stage_model_id(picked) == DEV and warm_group(picked) == DEV
    with pytest.raises(ValueError, match="cannot run the Stage method 'clay'"):
        stage_model_id(StageShot(stage_id="s", camera_id="c", passes=PASSES, model_id="zimage-bf16"))        # refused by name, with the list
    with pytest.raises(ValueError, match="cannot run the Stage method 'refcontrol'"):
        stage_model_id(StageShot(stage_id="s", camera_id="c", passes=PASSES, method="refcontrol", model_id=DEV, refs=[RefImage(asset_id="a")]))
    with pytest.raises(ValueError):
        stage_model_id(picked, "open")                                                                         # not offered under open
    assert parse_recipe({"kind": "stage_shot", "stage_id": "s", "camera_id": "c", "passes": {"clay": "a"}, "model_id": DEV}).model_id == DEV


def test_a_guest_runs_the_clay_method_at_its_edit_settings(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    dev = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, prompt_text="a rainy alley at night", model_id=DEV,
                    refs=[RefImage(asset_id="ast_hero", note="the hero"), RefImage(asset_id="ast_tavern", note="the tavern's sign")])
    c = graphs.compile_recipe(dev, roster, object_info, 7, "loom2/shot", ref_files=REFS, inputs=INPUTS)
    assert c.problems == [], c.problems
    kinds = [n["class_type"] for n in c.graph.values()]
    assert kinds.count("ReferenceLatent") == 3 and "FluxGuidance" in kinds and kinds.count("LoraLoaderModelOnly") == 1   # image 1 + 2 refs; the guidance; the Turbo LoRA
    assert c.graph["12"]["inputs"]["guidance"] == 4.0 and c.graph["10"]["inputs"]["positive"] == ["12", 0]
    assert c.graph["10"]["inputs"]["steps"] == 8 and c.graph["10"]["inputs"]["cfg"] == 1.0 and c.graph["6"]["inputs"]["text"] == ""
    assert c.graph["100"]["inputs"]["image"] == INPUTS["clay"] and c.serialized_prompt.startswith(graphs.STAGE_CLAY_LEAD)
    assert c.summary["model_id"] == DEV and c.summary["guidance"] == 4.0 and c.summary["turbo"] is True and c.summary["refs"] == 2
    assert {DEV, "flux2-turbo-lora", "mistral3-small-flux2-fp8", "flux2-vae"} <= set(graphs.recipe_weights(dev))
    # Klein's measured graph is as E10 ran it: no FluxGuidance, 4 steps
    klein = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, prompt_text="a rainy alley at night", refs=[RefImage(asset_id="ast_hero")])
    k = graphs.compile_recipe(klein, roster, object_info, 7, "loom2/shot", ref_files=REFS, inputs=INPUTS)
    assert "FluxGuidance" not in [n["class_type"] for n in k.graph.values()] and k.graph["10"]["inputs"]["steps"] == 4 and k.summary["guidance"] is None
    # the plan: dev's own Turbo estimate, said unmeasured; Klein's E10 figure
    p = plan(dev)
    assert p.model_id == DEV and p.warm_group == DEV and p.estimate["seconds"] == 102.8 and "reference latents" in p.estimate["source"] and p.params["max_refs"] == 9   # 40 s at 960×544 → 70.6 at 1280×720, + the pass and two ≈ 1 MP references at 8 steps
    assert plan(klein).estimate["seconds"] == 12.0 and "E10" in plan(klein).estimate["source"]


def test_capabilities_list_the_models_per_method(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    for variant, first, has_dev in (("full", "klein-9b", True), ("open", "klein-4b", False)):
        state = tmp_path / f"state-{variant}"
        AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                         "mounted_model_trees": [], "variant": variant})
        app = create_app(state)
        with TestClient(app) as cl:
            sc = cl.get("/capabilities", headers={"X-Loom-Token": app.state.services.app.token}).json()["stage"]
            models = sc["methods"]["clay"]["models"]
            ids = [m["id"] for m in models]
            assert ids[0] == first and (DEV in ids) == has_dev and models[0]["measured"] is (variant == "full") and models[0]["seconds"] == (12.0 if variant == "full" else 17.6)
            assert all({"id", "label", "short", "health", "seconds", "measured", "max_refs", "license", "approx_gb"} <= set(m) for m in models)
            if has_dev:
                d = next(m for m in models if m["id"] == DEV)
                assert d["measured"] is False and d["seconds"] == 70.6 and d["max_refs"] == 9                     # the card: dev's Turbo figure scaled to the Draft still
            if "refcontrol" in sc["methods"]:
                assert [m["id"] for m in sc["methods"]["refcontrol"]["models"]] == ["klein-base-9b"]


def test_the_sets_painting_model_and_the_reference_model(tmp_path: Path):
    assert set_model(None, "full") == "klein-9b" and set_model(PlaceSet(), "full") == "klein-9b"               # no card: the Fill default
    assert set_model(PlaceSet(model_id=DEV), "full") == DEV and set_model(PlaceSet(model_id=DEV), "full", "i2i") == DEV   # dev fills and refines
    assert set_model(PlaceSet(model_id="klein-9b"), "full", "i2i") == "klein-base-9b"                          # Klein 9B does not refine: the refine default
    assert set_model(PlaceSet(model_id="zimage-bf16"), "full") == "klein-9b"                                   # no Fill on it: the default
    assert set_model(PlaceSet(model_id=DEV), "open") == "klein-4b"                                              # not offered under open
    assert expand_spec("full").id == "klein-9b" and expand_spec("full", DEV).id == DEV and expand_spec("full", "zimage-bf16").id == "klein-9b"
    assert expand_spec("open", "klein-9b").id == "klein-4b"
    ws, cat, groups, _ = _setup(tmp_path)
    st = StoryStore(ws)
    hero = cat.ingest_file(_png(tmp_path / "h.png")).id
    p = st.create_profile("Mara", "character", groups, hero_asset_id=hero, appearance="Mara, a wiry courier")
    planned = plan_anim_ref(p, p.version(), "front", "full", width=1280, height=720, count=1, group_id="grp_c", model_id=DEV)
    assert planned[0][0]["model_id"] == DEV
    assert plan_anim_ref(p, p.version(), "front", "full", width=1280, height=720, count=1, group_id="grp_c")[0][0]["model_id"] == "klein-9b"


def test_a_clay_still_leads_its_deck_with_the_scenes_place(tmp_path: Path):
    """D186 follow-up (the author: "the still doesn't contain the background"): the set picture of the Cast place the scene's set is bound to
    is the still's image 2, said as the place in the prompt; not for the exact pose, not twice, not without a place."""
    from loom2.engine.graphs import stage_prompt
    from loom2.mentions import stage_place_ref
    from loom2.stages import StageObject, StageStore
    ws, cat, groups, _ = _setup(tmp_path)
    st = StoryStore(ws)
    hero = cat.ingest_file(_png(tmp_path / "quay.png")).id
    quay = st.create_profile("Quay", "place", groups, hero_asset_id=hero, appearance="a stone quay at dusk")
    stage = StageStore(ws).create("Harbour")
    bare = StageShot(stage_id=stage.id, camera_id=stage.cameras[0].id, passes=PASSES, refs=[RefImage(asset_id="ast_hero", note="the hero")])
    assert stage_place_ref(bare, ws, cat, st).refs == bare.refs                                                     # no set yet: untouched
    stage.objects.append(StageObject(id="set_1", kind="set", name="Quay", preset="built", profile_id=quay.id, version="v1"))
    StageStore(ws).save(stage)
    r = stage_place_ref(bare, ws, cat, st)
    assert [x.asset_id for x in r.refs] == [hero, "ast_hero"] and r.refs[0].mention == "place:Quay"                 # the place first (image 2), the author's deck after
    assert "Image 2 shows the place — Quay: its walls, floor, light and materials." in stage_prompt(r) and "Image 3 shows the hero." in stage_prompt(r)
    assert stage_place_ref(r, ws, cat, st).refs == r.refs                                                           # not twice
    exact = StageShot(stage_id=stage.id, camera_id=stage.cameras[0].id, passes=PASSES, method="refcontrol", refs=[RefImage(asset_id="ast_hero")])
    assert stage_place_ref(exact, ws, cat, st).refs == exact.refs                                                   # the exact pose's image 2 is the character's
    # a picture set (SC3): its picture
    stage.objects[-1] = StageObject(id="set_2", kind="set", name="Pier", preset="image", plate_asset_id=hero)
    StageStore(ws).save(stage)
    assert stage_place_ref(bare, ws, cat, st).refs[0].mention == "place:Pier"
