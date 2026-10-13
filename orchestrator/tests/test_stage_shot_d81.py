"""P13 ST3 (D78 / D81, 16 §7): Stage → image — the `StageShot` recipe resolves its method to E10's pair per variant, both graphs compile
against the engine's contract (the clay reference chain, the RefControl LoRA), the weights and lineage are right, the passes route turns
uploaded blobs into `stage-pass` assets on the stage's album page and records them on the document, and `/capabilities` describes the
methods."""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs  # noqa: E402
from loom2.engine.finishers import _parents  # noqa: E402
from loom2.engine.pipeline import placeholder_inputs, plan, preview_problems  # noqa: E402
from loom2.recipes import RefImage, StageShot, parse_recipe, stage_model_id, warm_group  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402

PASSES = {"clay": "ast_clay", "pose": "ast_pose", "depth": "ast_depth"}
INPUTS = {"clay": "alley-rain_s20261004.png", "pose": "alley-rain_s20261004.png"}
REFS = {"ast_hero": "alley-rain_s20261004.png", "ast_tavern": "alley-rain_s20261004.png"}


def test_methods_resolve_per_variant():
    clay = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES)
    assert clay.method == "clay" and stage_model_id(clay) == clay.model_id == "klein-9b"
    assert stage_model_id(clay, "open") == "klein-4b" and warm_group(clay, "open") == "klein-4b"      # D26: 9B is flux-nc
    exact = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, method="refcontrol", refs=[RefImage(asset_id="ast_hero")])
    assert stage_model_id(exact) == "klein-base-9b" and warm_group(exact) == "klein-base-9b"
    with pytest.raises(ValueError):
        stage_model_id(exact, "open")                                                               # base 9B is not offered under open
    assert parse_recipe({"kind": "stage_shot", "stage_id": "s", "camera_id": "c", "passes": {"clay": "a"}}).model_id == "klein-9b"
    with pytest.raises(ValueError):
        parse_recipe({"kind": "stage_shot", "stage_id": "s", "camera_id": "c", "passes": {"clay": "a"}, "method": "depth"})


def test_both_graphs_compile_against_the_engine(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    clay = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, prompt_text="a rainy alley at night",
                     refs=[RefImage(asset_id="ast_hero", note="the hero"), RefImage(asset_id="ast_tavern", note="the tavern's sign.")])
    c = graphs.compile_recipe(clay, roster, object_info, 7, "loom2/shot", ref_files=REFS, inputs=INPUTS)
    assert c.problems == [], c.problems
    kinds = [n["class_type"] for n in c.graph.values()]
    assert kinds.count("ReferenceLatent") == 3 and "LoraLoaderModelOnly" not in kinds and "EmptyFlux2LatentImage" in kinds
    assert c.graph["100"]["inputs"]["image"] == INPUTS["clay"]                                      # image 1 is the clay pass
    assert (c.graph["9"]["inputs"]["width"], c.graph["9"]["inputs"]["height"]) == (1280, 720)
    assert c.graph["2"]["class_type"] == "CLIPLoaderGGUF"                                           # D31
    assert c.graph["6"]["inputs"]["text"] == ""                                                     # distilled: no negative
    assert c.serialized_prompt.startswith(graphs.STAGE_CLAY_LEAD)
    assert "Image 2 shows the hero." in c.serialized_prompt and "Image 3 shows the tavern's sign." in c.serialized_prompt
    assert c.serialized_prompt.endswith("a rainy alley at night")
    assert c.summary["method"] == "clay" and c.summary["image1"] == "clay" and c.summary["refs"] == 2 and c.output_node == "99"
    exact = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, method="refcontrol", prompt_text="a rainy alley at night",
                      refs=[RefImage(asset_id="ast_hero"), RefImage(asset_id="ast_tavern")], width=1920, height=1080)
    c = graphs.compile_recipe(exact, roster, object_info, 7, "loom2/shot", ref_files=REFS, inputs=INPUTS)
    assert c.problems == [], c.problems
    kinds = [n["class_type"] for n in c.graph.values()]
    assert kinds.count("ReferenceLatent") == 2 and kinds.count("LoraLoaderModelOnly") == 1 and "ImageScaleToTotalPixels" in kinds
    assert c.graph["4"]["inputs"]["lora_name"].endswith("refcontrol_v2_poses.safetensors") and c.graph["4"]["inputs"]["strength_model"] == 0.9
    assert c.graph["100"]["inputs"]["image"] == INPUTS["pose"]                                      # image 1 is the pose pass (D81)
    assert c.graph["10"]["inputs"]["steps"] == 30 and c.graph["10"]["inputs"]["cfg"] == 4.0        # E10's base settings
    assert c.graph["6"]["inputs"]["text"] == graphs.STAGE_NEG
    assert (c.graph["9"]["inputs"]["width"], c.graph["9"]["inputs"]["height"]) == (1920, 1072)     # snapped to 16
    assert c.serialized_prompt == "apply pose from image 1 with reference from image 2. a rainy alley at night"
    assert c.summary["refs"] == 1 and c.summary["refs_dropped"] == 1                               # one reference only (image 2)
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(StageShot(stage_id="s", camera_id="c", passes=PASSES, method="refcontrol"), roster, object_info, 1, "x", inputs=INPUTS)
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(clay, roster, object_info, 1, "x", ref_files=REFS, inputs={"pose": "p.png"})       # the clay pass is missing


def test_weights_lineage_plan_and_preview(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    clay = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, refs=[RefImage(asset_id="ast_hero")])
    assert {"klein-9b", "qwen3-8b-q4km", "flux2-vae"} <= set(graphs.recipe_weights(clay)) and "refcontrol-v2-poses" not in graphs.recipe_weights(clay)
    exact = StageShot(stage_id="stg_1", camera_id="cam_1", passes=PASSES, method="refcontrol", refs=[RefImage(asset_id="ast_hero"), RefImage(asset_id="ast_x")])
    assert {"klein-base-9b", "refcontrol-v2-poses"} <= set(graphs.recipe_weights(exact))
    assert _parents(clay) == ["ast_clay", "ast_hero"] and _parents(exact) == ["ast_pose", "ast_hero"]  # the pass used + the kept references
    p = plan(clay)
    assert p.kind == "stage_shot" and p.model_id == "klein-9b" and p.needs == ["refs", "passes"] and p.params["image1"] == "clay"
    assert p.estimate["seconds"] == 12.0 and "E10" in p.estimate["source"] and p.vram_gb >= 14 and p.warm_group == "klein-9b"
    assert p.params["max_refs"] == 3 and p.params["refs"] == 1
    p2 = plan(exact)
    assert p2.estimate["seconds"] == 74.0 and p2.params["refs_dropped"] == 1 and p2.params["image1"] == "pose"
    p3 = plan(StageShot(stage_id="s", camera_id="c", passes=PASSES), "open")
    assert p3.model_id == "klein-4b" and p3.estimate["seconds"] == 10.0 and "unmeasured" in p3.estimate["source"]
    with pytest.raises(graphs.CompileError):
        plan(StageShot(stage_id="s", camera_id="c", passes=PASSES, method="refcontrol"))
    ph = placeholder_inputs(clay, object_info)
    assert set(ph) == {"clay", "pose"} and ph["clay"] and ph["clay"] == ph["pose"]                 # an image the engine lists
    assert preview_problems(clay, roster, object_info) == []
    assert preview_problems(exact, roster, object_info) == []


def _png(colour: tuple[int, int, int]) -> bytes:
    im = Image.new("RGB", (64, 36), colour)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_passes_route_places_assets_and_records_them(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        s = cl.post("/stages", json={"name": "Alley"}, headers=H).json()
        cam = s["cameras"][0]["id"]
        blobs = {}
        for name, colour in (("clay", (180, 180, 180)), ("depth", (40, 40, 40)), ("pose", (0, 0, 0)), ("mask", (255, 0, 0))):
            data = _png(colour)
            sha = hashlib.sha256(data).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=data, headers=H).status_code == 200
            blobs[name] = sha
        body = {"camera_id": cam, "revision": 0, "size": {"w": 64, "h": 36}, "passes": blobs, "keypoints": [[[1, 2, 1]] * 18], "legend": {"#ff0000": "m1"}}
        r = cl.post(f"/stages/{s['id']}/passes", json=body, headers=H)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["revision"] == 1 and doc["group_id"] and len(doc["passes"]) == 1
        entry = doc["passes"][0]
        assert entry["camera_id"] == cam and entry["revision"] == 0 and set(entry["assets"]) == {"clay", "depth", "pose", "mask"} and entry["keypoints"] == body["keypoints"]
        pose = cl.get(f"/assets/{entry['assets']['pose']}", headers=H).json()
        assert pose["lineage_kind"] == "stage-pass" and pose["suite"] == "stage" and pose["parents"] == [] and pose["w"] == 64
        assert pose["params"]["pass"] == "pose" and pose["params"]["stage_id"] == s["id"] and pose["params"]["keypoints"] == body["keypoints"]
        assert pose["origin"] == {"suite": "stage", "surface": "passes", "ref": s["id"], "payload": {"camera_id": cam}}
        mask = cl.get(f"/assets/{entry['assets']['mask']}", headers=H).json()
        assert mask["params"]["legend"] == {"#ff0000": "m1"} and "keypoints" not in mask["params"]
        page = cl.get(f"/groups/{doc['group_id']}", headers=H).json()
        assert page["group"]["name"] == "Stage · Alley" and {it["id"] for it in page["group"]["items"]} == set(entry["assets"].values())
        # a second render of the same camera replaces its entry, keeps the page; another camera adds one
        body2 = {**body, "revision": 1, "passes": {"clay": blobs["clay"]}}
        doc2 = cl.post(f"/stages/{s['id']}/passes", json=body2, headers=H).json()
        assert doc2["revision"] == 2 and len(doc2["passes"]) == 1 and doc2["passes"][0]["revision"] == 1 and doc2["group_id"] == doc["group_id"]
        assert cl.post(f"/stages/{s['id']}/passes", json={**body, "camera_id": "cam_ghost"}, headers=H).status_code == 422
        assert cl.post(f"/stages/{s['id']}/passes", json={**body, "passes": {"clay": "0" * 64}}, headers=H).status_code == 422
        assert cl.post(f"/stages/{s['id']}/passes", json={**body, "passes": {"beauty": blobs["clay"]}}, headers=H).status_code == 422
        # a client save on the stale revision is refused (the client takes the returned document instead)
        assert cl.put(f"/stages/{s['id']}", json={**doc, "revision": 0}, headers=H).status_code == 409
        assert cl.put(f"/stages/{s['id']}", json={**doc2, "name": "Alley 2"}, headers=H).json()["group_id"] == doc["group_id"]   # group_id is the server's


def test_capabilities_describe_the_methods(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    for variant, methods, model in (("full", {"clay", "refcontrol"}, "klein-9b"), ("open", {"clay"}, "klein-4b")):
        state = tmp_path / variant / "state"
        AppState(state).update_settings({"models_root": str(tmp_path / variant / "models"), "mounted_model_trees": [], "variant": variant})
        _pin_review().full_roster(tmp_path / variant / "models")
        with TestClient(create_app(state)) as cl:
            sc = cl.get("/capabilities").json()["stage"]
            assert set(sc["methods"]) == methods and sc["default"] == "clay" and sc["passes"] == ["clay", "depth", "normal", "pose", "mask"]
            assert sc["methods"]["clay"]["model_id"] == model and sc["methods"]["clay"]["image1"] == "clay" and sc["methods"]["clay"]["max_refs"] == 3
            assert sc["methods"]["clay"]["measured"] == (variant == "full")
            if variant == "full":
                rc = sc["methods"]["refcontrol"]
                assert rc["model_id"] == "klein-base-9b" and rc["seconds"] == 74.0 and rc["image1"] == "pose" and rc["max_refs"] == 1 and rc["health"] != "missing"
            pv = cl.post("/recipes/preview", json={"recipe": {"kind": "stage_shot", "stage_id": "s", "camera_id": "c", "passes": {"clay": "ast_x"}}}).json()
            assert pv["kind"] == "stage_shot" and pv["params"]["method"] == "clay" and pv["needs"] == ["passes"] and pv["model_id"] == model
