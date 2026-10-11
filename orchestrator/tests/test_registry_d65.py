"""D65 (ArtCraft P1): model knowledge as data.

- the registry refuses a spec that names a weight the roster does not know;
- acceptance: a spec file in a folder named by LOOM2_MODEL_SPECS (a fake Klein variant, its weight declared in the file) appears in
  /capabilities, compiles and runs its defaults — without a line of Python or frontend code;
- the size policy answers 422 {field, value, allowed, message} at submission and in the preview;
- the sweep: every spec × tier / mode / preset compiles against the pinned object_info with zero contract problems, and the
  estimates grow with pixels and frames.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loom2.api import create_app
from loom2.config import AppState
from loom2.engine import graphs
from loom2.engine.graphs import compile_recipe, estimate_i2v_seconds, estimate_seconds
from loom2.models import registry
from loom2.recipes import I2I, I2V, Beat, Inpaint, Segment, T2I, Upscale
from loom2.roster import ROSTER, ROSTER_BY_ID
from test_graph_parity_d64 import _pin_review

FAKE = '''
[[model]]
id = "klein-9b-test"
family = "klein"
label = "Klein 9B test"
order = 9
graph = "klein"
roles.te = { default = "qwen3-8b-q4km" }
roles.vae = "flux2-vae"
sampling = { steps = 4, guidance = 1.0, cfg = 1.0, weight_dtype = "fp8_e4m3fn", distilled = true, json_prompt = false }
recipes = { t2i = true, inpaint = ["fill", "fill_match", "remove", "outpaint"] }
inputs = { refs_max = 4 }
geometry = { size_mult = 16, tiers = { draft = [1280, 720] } }
estimates = { vram_gb = 15.0, base_seconds = 18.0, doc_seconds = 28.0 }
weight = { name = "flux-2-klein-9b-test.safetensors", folder = "diffusion_models", role = "transformer", license = "test", variants = ["full", "open"] }
'''


@pytest.fixture
def extra_specs(tmp_path: Path, monkeypatch):
    """Point the registry at an extra folder; undo the roster entry a spec added and reload afterwards."""
    d = tmp_path / "specs"
    d.mkdir()
    monkeypatch.setenv("LOOM2_MODEL_SPECS", str(d))
    before = {e.id for e in ROSTER}
    yield d
    monkeypatch.delenv("LOOM2_MODEL_SPECS")
    for e in [e for e in ROSTER if e.id not in before]:
        ROSTER.remove(e)
        ROSTER_BY_ID.pop(e.id, None)
    registry.load()


def test_a_spec_naming_an_unknown_weight_fails_at_load(extra_specs: Path):
    (extra_specs / "bad.toml").write_text(FAKE.replace('roles.vae = "flux2-vae"', 'roles.vae = "no-such-vae"'), encoding="utf-8")
    with pytest.raises(registry.RegistryError, match="no-such-vae"):
        registry.load()


def test_a_spec_file_adds_a_model_without_code(extra_specs: Path, tmp_path: Path, object_info: dict):
    (extra_specs / "klein-test.toml").write_text(FAKE, encoding="utf-8")
    registry.load()
    assert "klein-9b-test" in registry.SPECS and ROSTER_BY_ID["klein-9b-test"].folder == "diffusion_models"
    # it compiles once its weight is on disk and the engine lists it
    roster = _pin_review().full_roster(tmp_path / "models")
    info = copy.deepcopy(object_info)
    info["UNETLoader"]["input"]["required"]["unet_name"][0].append("flux-2-klein-9b-test.safetensors")
    for r in (T2I(model_id="klein-9b-test", prompt_text="a cat"), ):
        c = compile_recipe(r, roster, info, 1, "loom2/t")
        assert c.problems == [] and c.summary["steps"] == 4
    c = compile_recipe(Inpaint(document_id="d", model_id="klein-9b-test", mode="fill_match", prompt_text="x"), roster, info, 1, "loom2/t",
                       inputs={"image": "alley-rain_s20261004.png", "mask": "alley-rain_s20261004.png", "w": 960, "h": 544})
    assert c.problems == [] and c.summary["model_id"] == "klein-9b-test"           # it runs ICM itself (its spec lists fill_match)
    # it appears in /capabilities, ordered, with its blocks — Generate lists caps.models by `order`
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        caps = cl.get("/capabilities").json()
        m = caps["models"]["klein-9b-test"]
        assert m["label"] == "Klein 9B test" and m["order"] == 9 and m["recipes"]["t2i"] and m["license"] == "test"
        assert caps["defaults"]["t2i"] == registry.default_model("t2i", caps["variant"]) != "klein-9b-test"   # the defaults did not move


def test_size_policy_answers_a_field_named_422(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        t2i = cl.get("/capabilities").json()["defaults"]["t2i"]                      # the variant's default model (CI runs open and full)
        bad = {"kind": "t2i", "model_id": t2i, "prompt_text": "x", "width": 950, "height": 544, "size_policy": "error"}
        for r in (cl.post("/jobs", json={"recipe": bad}), cl.post("/recipes/preview", json={"recipe": bad})):
            assert r.status_code == 422
            d = r.json()["detail"]
            assert d["field"] == "width" and d["value"] == 950 and d["allowed"] == [944, 960] and "grid" in d["message"]
        ok = cl.post("/recipes/preview", json={"recipe": {**bad, "size_policy": "snap_down"}}).json()
        assert (ok["width"], ok["height"]) == (944, 544)


def test_sweep_every_spec_compiles(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    img = {"image": "alley-rain_s20261004.png", "mask": "alley-rain_s20261004.png", "w": 960, "h": 544}
    compiled = 0

    def ok(recipe, inputs=None, refs=None):
        nonlocal compiled
        c = compile_recipe(recipe, roster, object_info, 1, "loom2/sweep", ref_files=refs, inputs=inputs)
        assert c.problems == [], (recipe.kind, getattr(recipe, "model_id", ""), c.problems)
        compiled += 1
        return c

    for spec in registry.image_specs():
        if spec.recipes.t2i:
            secs = []
            for tier, (w, h) in sorted(spec.geometry.tiers.items(), key=lambda kv: kv[1][0] * kv[1][1]):
                r = T2I(model_id=spec.id, prompt_text="a cat", width=w, height=h)
                ok(r)
                secs.append(estimate_seconds(r)["seconds"])
                if spec.sampling.turbo:
                    ok(T2I(model_id=spec.id, prompt_text="a cat", width=w, height=h, turbo=True))
            assert secs == sorted(secs), (spec.id, secs)                         # more pixels, more time
        for mode in spec.recipes.inpaint:
            ok(Inpaint(document_id="d", model_id=spec.id, mode=mode, prompt_text="x", outpaint={"right": 240} if mode == "outpaint" else None), img)
        if spec.recipes.i2i:
            ok(I2I(document_id="d", model_id=spec.id, source="visible", strength=0.3), img)
            ok(Upscale(document_id="d", model_id=registry.default_model("upscale"), source="visible", refine=True, refine_model_id=spec.id), img)
    ok(Inpaint(document_id="d", mode="fill_hero", prompt_text="x"), img)
    for spec in registry.SPECS.values():
        if spec.recipes.upscale_factor:
            assert graphs.upscale_factor(spec.id) == spec.recipes.upscale_factor
            ok(Upscale(document_id="d", model_id=spec.id, source="visible"), img)
        for mode in spec.recipes.segment:
            ok(Segment(document_id="d", model_id=spec.id, mode=mode, text="a woman"), {**img, "points": [{"x": 10, "y": 10, "label": 1}], "box": [1, 1, 50, 50]})
    for spec in registry.video_specs():
        assert spec.video is not None
        for preset in spec.video.presets:
            frames_secs = []
            for frames in (spec.geometry.frames, (spec.geometry.frames or 81) * 2 - 1):
                r = I2V(start_asset="a", model_id=spec.id, preset=preset, frames=frames)
                ok(r, {"start": "alley-rain_s20261004.png"})
                frames_secs.append(estimate_i2v_seconds(r)["seconds"])
            assert frames_secs[0] < frames_secs[1], (spec.id, preset, frames_secs)  # more frames, more time
            if spec.recipes.flf:
                ok(I2V(start_asset="a", end_asset="b", model_id=spec.id, preset=preset), {"start": "alley-rain_s20261004.png", "end": "captain-cabin_s20261004.png"})
            if spec.recipes.beats:
                ok(I2V(start_asset="a", end_asset="b", model_id=spec.id, preset=preset, beats=[Beat(frame=20, asset_id="k")]),
                   {"start": "alley-rain_s20261004.png", "end": "captain-cabin_s20261004.png", "beats": {"k": "01-remove-crates.png"}})
    assert compiled >= 40
